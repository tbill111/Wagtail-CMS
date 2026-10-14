"""Nạp dữ liệu thật cho TH2 vào SmartCRM (checklist 01 – "dự báo từ dữ liệu thực tế").

    python manage.py import_th2_data --retail data/th2/online_retail_II.xlsx \
        --reviews data/th2/vi_sentiment_train.csv data/th2/vi_sentiment_test.csv [--clear]

Bán hàng: Online Retail II (UCI, CC BY 4.0, https://doi.org/10.24432/C5CG6D) – giao dịch thật của một shop online ở Anh,
01/12/2009 – 09/12/2011. Quy ước (docs/th2/HOP_DONG_DU_LIEU.md mục 3):
  - lấy mẫu --customers khách (mặc định 2.000) có mã khách, random_state=42;
  - dời thời gian +14 năm (giữ nguyên tháng → giữ mùa vụ), giờ gốc coi là giờ Việt Nam;
  - 1 GBP = 33.000 VNĐ; hoá đơn mã "C…" là đơn Huỷ, còn lại Hoàn thành;
  - chỉ giữ mã hàng bắt đầu bằng chữ số (bỏ phí ship, chiết khấu, phí ngân hàng…), giá > 0;
  - hai sheet của file trùng 1.088 hoá đơn tháng 12/2010: bỏ bản ở sheet đầu.
Văn bản: nhận xét điện thoại tiếng Việt chấm 1–5 sao (Hugging Face anotherpolarbear/vietnamese-sentiment-analysis, MIT).
1–2 sao = tiêu cực, 3 = trung lập, 4–5 = tích cực. Lấy mẫu phân tầng --reviews-count câu (mặc định 3.000), gắn NGẪU NHIÊN
cho các khách đã mua – việc gắn này là nhân tạo, báo cáo phải ghi rõ.
"""

from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Max, Min
from django.utils import timezone

from crm.models import Customer, InteractionLog, Order, OrderItem, Product
from insights.conf import CHURN_WINDOW_DAYS, RANDOM_STATE
from insights.models import ModelRun, SentimentLabel

GBP_TO_VND = 33_000
YEAR_SHIFT = 14
SKU_PREFIX = "UK-"
EMAIL_DOMAIN = "khach.smartcrm.local"
REVIEW_SOURCE = "anotherpolarbear/vietnamese-sentiment-analysis (Hugging Face, MIT) – điểm 1–5 sao"
STAR_TO_LABEL = {1: "negative", 2: "negative", 3: "neutral", 4: "positive", 5: "positive"}
CHANNELS = [(InteractionLog.Channel.EMAIL, 0.4), (InteractionLog.Channel.CHAT, 0.4),
            (InteractionLog.Channel.PHONE, 0.1), (InteractionLog.Channel.IN_PERSON, 0.1)]
RETAIL_COLUMNS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
BATCH = 5000


@contextmanager
def keep_created_at(*models):
    """Tạm tắt auto_now_add của created_at để ghi đúng ngày lịch sử khi bulk_create."""
    fields = [model._meta.get_field("created_at") for model in models]
    for field in fields:
        field.auto_now_add = False
    try:
        yield
    finally:
        for field in fields:
            field.auto_now_add = True


def load_retail(path):
    """Đọc Online Retail II (.xlsx gốc hoặc .csv cùng cột), bỏ hoá đơn trùng giữa 2 sheet."""
    path = Path(path)
    if not path.exists():
        raise CommandError(f"Không thấy file {path}. Tải từ https://archive.ics.uci.edu/dataset/502/online+retail+ii")
    dtype = {"Invoice": str, "StockCode": str, "Description": str}
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=dtype, parse_dates=["InvoiceDate"])
    cache = path.with_suffix(".clean.csv")
    if cache.exists() and cache.stat().st_mtime >= path.stat().st_mtime:
        return pd.read_csv(cache, dtype=dtype, parse_dates=["InvoiceDate"])
    sheets = list(pd.read_excel(path, sheet_name=None, dtype=dtype).values())
    later_invoices = set()
    frames = []
    for sheet in reversed(sheets):  # sheet sau được ưu tiên, sheet trước bỏ hoá đơn đã có ở sheet sau
        frames.append(sheet[~sheet["Invoice"].isin(later_invoices)])
        later_invoices |= set(sheet["Invoice"])
    data = pd.concat(reversed(frames), ignore_index=True)[RETAIL_COLUMNS]
    data.to_csv(cache, index=False)
    return data


def clean_retail(raw):
    data = raw.dropna(subset=["Customer ID"]).copy()
    data["Invoice"] = data["Invoice"].astype(str).str.strip()
    data["StockCode"] = data["StockCode"].astype(str).str.strip().str.upper()
    data["cancelled"] = data["Invoice"].str.startswith("C")
    data = data[data["StockCode"].str.match(r"^\d") & (data["Price"] > 0)]
    data = data[(data["cancelled"] & (data["Quantity"] < 0)) | (~data["cancelled"] & (data["Quantity"] > 0))]
    data["Quantity"] = data["Quantity"].abs().astype(int)
    data["customer_ref"] = data["Customer ID"].astype(int)
    data["unit_price"] = (data["Price"] * GBP_TO_VND).round().astype("int64")
    data["moment"] = (data["InvoiceDate"] + pd.DateOffset(years=YEAR_SHIFT)).dt.tz_localize(settings.TIME_ZONE)
    data["Description"] = data["Description"].fillna("").str.strip()
    return data


def load_reviews(paths):
    frames = []
    for path in paths:
        if not Path(path).exists():
            raise CommandError(f"Không thấy file {path}.")
        frames.append(pd.read_csv(path))
    data = pd.concat(frames, ignore_index=True)
    if not {"comment", "label"} <= set(data.columns):
        raise CommandError("File nhận xét phải có cột 'comment' và 'label' (1–5 sao).")
    data["comment"] = data["comment"].astype(str).str.strip()
    data = data[data["comment"].str.len() > 0].drop_duplicates("comment")
    data["sentiment"] = data["label"].map(STAR_TO_LABEL)
    return data.dropna(subset=["sentiment"])


class Command(BaseCommand):
    help = "Nạp dữ liệu thật (Online Retail II + nhận xét tiếng Việt có nhãn) cho TH2."

    def add_arguments(self, parser):
        parser.add_argument("--retail", required=True, help="online_retail_II.xlsx (hoặc .csv cùng cột).")
        parser.add_argument("--reviews", nargs="+", required=True, help="CSV có cột comment, label (1–5 sao).")
        parser.add_argument("--customers", type=int, default=2000, help="Số khách lấy mẫu (mặc định 2000).")
        parser.add_argument("--reviews-count", type=int, default=3000, help="Số nhận xét nạp (mặc định 3000).")
        parser.add_argument("--clear", action="store_true", help="Xoá khách, đơn, tương tác, kết quả AI cũ trước.")
        parser.add_argument("--allow-any-db", action="store_true",
                            help="Cho chạy trên CSDL không có đuôi _th2 (chỉ dùng khi biết mình đang làm gì).")

    def handle(self, *args, **options):
        db_name = str(connection.settings_dict["NAME"])
        if not (db_name.endswith("_th2") or options["allow_any_db"]):
            raise CommandError(f"CSDL hiện tại là '{db_name}'. Chỉ nạp vào CSDL TH2 (DB_NAME=smartcrm_th2).")
        if Customer.objects.exists() and not options["clear"]:
            raise CommandError("CSDL đã có khách hàng. Thêm --clear để xoá dữ liệu cũ rồi nạp lại.")

        self.stdout.write("Đọc Online Retail II…")
        sales = clean_retail(load_retail(options["retail"]))
        reviews = load_reviews(options["reviews"])

        refs = pd.Series(sorted(sales.loc[~sales["cancelled"], "customer_ref"].unique()))
        if len(refs) < options["customers"]:
            raise CommandError(f"Chỉ có {len(refs)} khách hợp lệ, ít hơn --customers={options['customers']}.")
        chosen = set(refs.sample(n=options["customers"], random_state=RANDOM_STATE))
        sales = sales[sales["customer_ref"].isin(chosen)]

        with transaction.atomic():
            if options["clear"]:
                self.clear()
            with keep_created_at(Customer, Product, Order, InteractionLog):
                products = self.create_products(sales)
                customers = self.create_customers(sales)
                n_orders, n_items = self.create_orders(sales, customers, products)
                n_reviews = self.create_interactions(reviews, customers, options["reviews_count"])
            reference = timezone.localtime(Order.objects.aggregate(m=Max("created_at"))["m"]).date()
            churned = self.update_status(reference)

        completed = sales[~sales["cancelled"]]
        revenue = int((completed["Quantity"] * completed["unit_price"]).sum())
        self.stdout.write(self.style.SUCCESS(
            f"Đã nạp {len(customers)} khách, {n_orders} đơn ({sales.loc[sales['cancelled'], 'Invoice'].nunique()} đơn "
            f"huỷ), {n_items} dòng sản phẩm, {len(products)} sản phẩm, {n_reviews} nhận xét có nhãn."))
        self.stdout.write(f"Khoảng thời gian: {sales['moment'].min():%d/%m/%Y} – {sales['moment'].max():%d/%m/%Y} "
                          f"(ngày tham chiếu {reference:%d/%m/%Y}).")
        self.stdout.write(f"Doanh thu đơn Hoàn thành: {revenue:,} VNĐ · khách Đã rời bỏ (≥ {CHURN_WINDOW_DAYS} ngày "
                          f"không mua): {churned}.")

    def clear(self):
        ModelRun.objects.all().delete()
        InteractionLog.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        Customer.objects.all().delete()
        Product.objects.filter(sku__startswith=SKU_PREFIX).delete()
        self.stdout.write("Đã xoá dữ liệu cũ.")

    def create_products(self, sales):
        rows = []
        for code, group in sales.groupby("StockCode"):
            names = group["Description"][group["Description"] != ""]
            name = names.mode().iloc[0] if len(names) else code
            rows.append(Product(
                sku=f"{SKU_PREFIX}{code}"[:30], name=name[:200], price=int(group["unit_price"].median()),
                track_stock=False, stock=0, min_stock=0, created_at=group["moment"].min(),
            ))
        Product.objects.bulk_create(rows, batch_size=BATCH)
        return dict(Product.objects.filter(sku__startswith=SKU_PREFIX).values_list("sku", "pk"))

    def create_customers(self, sales):
        first = sales.groupby("customer_ref")["moment"].min()
        rows = [
            Customer(name=f"Khách UK-{ref}", email=f"uk{ref}@{EMAIL_DOMAIN}", source=Customer.Source.WEBSITE,
                     status=Customer.Status.CUSTOMER, created_at=moment)
            for ref, moment in first.items()
        ]
        Customer.objects.bulk_create(rows, batch_size=BATCH)
        return {int(email[2:].split("@")[0]): pk for email, pk in
                Customer.objects.filter(email__endswith=f"@{EMAIL_DOMAIN}").values_list("email", "pk")}

    def create_orders(self, sales, customers, products):
        invoices = (sales.groupby("Invoice")
                    .agg(moment=("moment", "min"), customer_ref=("customer_ref", "first"),
                         cancelled=("cancelled", "first"), country=("Country", "first"))
                    .reset_index().sort_values(["moment", "Invoice"]))
        invoices["day"] = invoices["moment"].dt.strftime("%Y%m%d")
        invoices["seq"] = invoices.groupby("day").cumcount() + 1
        orders = [
            Order(code=f"DH-{row.day}-{row.seq:04d}", customer_id=customers[row.customer_ref],
                  status=Order.Status.CANCELLED if row.cancelled else Order.Status.COMPLETED,
                  note=f"Online Retail II – hoá đơn {row.Invoice} – {row.country}", created_at=row.moment)
            for row in invoices.itertuples()
        ]
        Order.objects.bulk_create(orders, batch_size=BATCH)
        codes = dict(Order.objects.values_list("code", "pk"))
        order_pk = {row.Invoice: codes[f"DH-{row.day}-{row.seq:04d}"] for row in invoices.itertuples()}

        # Gộp các dòng cùng mã hàng và cùng đơn giá trong một hoá đơn (giữ đúng doanh thu)
        lines = (sales.groupby(["Invoice", "StockCode", "unit_price"], sort=False)
                 .agg(quantity=("Quantity", "sum"), name=("Description", "first")).reset_index())
        lines["sort_order"] = lines.groupby("Invoice").cumcount()
        items = [
            OrderItem(order_id=order_pk[row.Invoice], product_id=products[f"{SKU_PREFIX}{row.StockCode}"[:30]],
                      product_name=(row.name or row.StockCode)[:200], quantity=int(row.quantity),
                      unit_price=int(row.unit_price), sort_order=int(row.sort_order))
            for row in lines.itertuples()
        ]
        OrderItem.objects.bulk_create(items, batch_size=BATCH)
        return len(orders), len(items)

    def create_interactions(self, reviews, customers, count):
        rng = np.random.default_rng(RANDOM_STATE)
        frac = min(1.0, count / len(reviews))
        # Lấy mẫu phân tầng: giữ nguyên tỉ lệ tích cực / trung lập / tiêu cực của bộ dữ liệu
        sample = (reviews.groupby("sentiment").sample(frac=frac, random_state=RANDOM_STATE)
                  .sample(frac=1, random_state=RANDOM_STATE).head(count))

        # Mỗi nhận xét gắn cho một khách đã mua, thời điểm nằm trong khoảng khách đó còn mua hàng (+30 ngày)
        spans = {row["customer_id"]: (row["first"], row["last"]) for row in
                 Order.objects.filter(status=Order.Status.COMPLETED).values("customer_id")
                 .annotate(first=Min("created_at"), last=Max("created_at"))}
        buyers = sorted(spans)
        end = Order.objects.aggregate(m=Max("created_at"))["m"]
        channels = [str(channel) for channel, _ in CHANNELS]
        weights = [weight for _, weight in CHANNELS]

        logs = []
        for comment in sample["comment"]:
            pk = buyers[rng.integers(len(buyers))]
            first, last = spans[pk]
            stop = min(last + timedelta(days=30), end)
            moment = first + (stop - first) * float(rng.random())
            logs.append(InteractionLog(customer_id=pk, channel=str(rng.choice(channels, p=weights)),
                                       customer_message=comment, created_at=moment))
        created = InteractionLog.objects.bulk_create(logs, batch_size=BATCH)
        SentimentLabel.objects.bulk_create(
            [SentimentLabel(interaction=log, label=label, source=REVIEW_SOURCE)
             for log, label in zip(created, sample["sentiment"])], batch_size=BATCH)
        return len(created)

    def update_status(self, reference):
        cutoff = reference - timedelta(days=CHURN_WINDOW_DAYS)
        last = Order.objects.filter(status=Order.Status.COMPLETED).values("customer_id").annotate(m=Max("created_at"))
        churned = [row["customer_id"] for row in last if timezone.localtime(row["m"]).date() < cutoff]
        Customer.objects.filter(pk__in=churned).update(status=Customer.Status.CHURNED)
        return len(churned)
