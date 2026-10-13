"""Kiểm tra tính chính xác số liệu hiển thị trên Apache Superset (TH1 · checklist 05).

    python manage.py verify_superset_data              # Wagtail (ORM) ↔ view analytics trong PostgreSQL
    python manage.py verify_superset_data --superset   # thêm cột: chạy cùng câu SQL QUA Superset (SQL Lab,
                                                       # tài khoản chỉ đọc superset_ro) để đối chiếu

Vế "Wagtail" dùng đúng các hàm của crm/analytics.py – nguồn số liệu của trang Tổng quan /crm/.
Vế "Superset" là câu SQL mà biểu đồ Superset chạy trên các view schema analytics.
Trả về mã lỗi 1 nếu có bất kỳ chỉ số nào lệch.
"""

import os
import secrets
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Count, Min, Q, Sum
from django.utils import timezone

from crm import analytics
from crm.models import Customer, Order, OrderItem, Product

DATABASE_NAME = "SmartCRM – Wagtail (chỉ đọc)"  # trùng superset/bootstrap_dashboard.py


def month_label(value):
    return f"T{value.month}/{value.year}"


def completed_revenue():
    return int(OrderItem.objects.filter(analytics.COMPLETED_ITEMS).aggregate(t=Sum(analytics.LINE_TOTAL))["t"] or 0)


def cancel_rate():
    total = Order.objects.filter(items__isnull=False).distinct().count()
    cancelled = Order.objects.filter(items__isnull=False, status=Order.Status.CANCELLED).distinct().count()
    return round(cancelled / total, 4) if total else 0


def status_counts():
    return [(row["label"], row["value"]) for row in analytics.customers_by_status()]


def buyers_summary():
    """Số khách đã có đơn Hoàn thành và tổng chi tiêu của họ – phải khớp tổng của view RFM."""
    buyers = OrderItem.objects.filter(analytics.COMPLETED_ITEMS).values("order__customer").distinct().count()
    return [("Số khách đã mua", buyers), ("Tổng chi tiêu", completed_revenue())]


def churn_by_source():
    """Tỉ lệ rời bỏ = khách Đã rời bỏ / khách từng mua (Đã mua hàng + Đã rời bỏ), theo nguồn khách."""
    labels = dict(Customer.Source.choices)
    rows = Customer.objects.values("source").annotate(
        churned=Count("id", filter=Q(status=Customer.Status.CHURNED)),
        bought=Count("id", filter=Q(status__in=[Customer.Status.CUSTOMER, Customer.Status.CHURNED])),
    )
    return sorted((labels[r["source"]], round(r["churned"] / r["bought"], 4)) for r in rows if r["bought"])


def cohort_sizes():
    """Số khách theo tháng có đơn Hoàn thành đầu tiên (giờ Việt Nam) – cột 'tháng 0' của heatmap cohort."""
    firsts = (OrderItem.objects.filter(analytics.COMPLETED_ITEMS)
              .values("order__customer").annotate(first=Min("order__created_at")))
    sizes = {}
    for row in firsts:
        month = timezone.localtime(row["first"]).strftime("%Y-%m")
        sizes[month] = sizes.get(month, 0) + 1
    return sorted(sizes.items())


# (tên chỉ số, hàm lấy số liệu từ Wagtail, SQL trên view analytics, hàm chuẩn hoá kết quả SQL)
def build_checks():
    months = analytics.monthly_revenue(12)
    first_month = months[0]["label"][1:].split("/")
    since = f"{first_month[1]}-{int(first_month[0]):02d}-01"
    labels = dict(Customer.Status.choices)
    return [
        ("Tổng doanh thu (đơn Hoàn thành)", completed_revenue,
         "SELECT SUM(line_total) FROM analytics.v_order_lines WHERE is_completed",
         lambda rows: int(rows[0][0] or 0)),
        ("Số đơn hoàn thành", lambda: Order.objects.filter(status=Order.Status.COMPLETED).count(),
         "SELECT COUNT(DISTINCT order_id) FROM analytics.v_order_lines WHERE is_completed",
         lambda rows: rows[0][0]),
        ("Tỉ lệ đơn huỷ", cancel_rate,
         "SELECT COUNT(DISTINCT CASE WHEN order_status = 'cancelled' THEN order_id END)::numeric"
         " / NULLIF(COUNT(DISTINCT order_id), 0) FROM analytics.v_order_lines",
         lambda rows: round(float(rows[0][0] or 0), 4)),
        ("Doanh thu 12 tháng gần nhất (từng tháng)",
         lambda: [(m["label"], m["value"]) for m in months if m["value"]],
         "SELECT date_trunc('month', order_date)::date AS m, SUM(line_total) FROM analytics.v_order_lines"
         f" WHERE is_completed AND order_date >= DATE '{since}' GROUP BY 1 ORDER BY 1",
         lambda rows: [(month_label(m), int(v)) for m, v in rows]),
        ("Số khách hàng theo trạng thái", status_counts,
         "SELECT customer_status, COUNT(*) FROM analytics.v_customers GROUP BY 1",
         lambda rows: [(label, dict(rows).get(value, 0)) for value, label in labels.items()]),
        ("Top 5 khách hàng theo chi tiêu",
         lambda: [(r["label"], r["value"]) for r in analytics.top_customers(5)],
         "SELECT customer_name, total_spent FROM analytics.v_customers WHERE total_spent > 0"
         " ORDER BY total_spent DESC, customer_name LIMIT 5",
         lambda rows: [(name, int(value)) for name, value in rows]),
        ("Top 5 sản phẩm bán chạy (số lượng)",
         lambda: [(r["sku"], r["value"]) for r in analytics.top_products(5)],
         "SELECT product_sku, sold_quantity FROM analytics.v_products WHERE sold_quantity > 0"
         " ORDER BY sold_quantity DESC, revenue DESC, product_name LIMIT 5",
         lambda rows: [(sku, int(qty)) for sku, qty in rows]),
        ("Sản phẩm sắp hết hàng",
         lambda: sorted(p["sku"] for p in analytics.low_stock_products()),
         "SELECT product_sku FROM analytics.v_products WHERE is_low_stock ORDER BY 1",
         lambda rows: sorted(r[0] for r in rows)),
        ("Tổng tồn kho (sản phẩm quản lý kho)",
         lambda: Product.objects.filter(track_stock=True).aggregate(s=Sum("stock"))["s"] or 0,
         "SELECT COALESCE(SUM(stock), 0) FROM analytics.v_products WHERE track_stock",
         lambda rows: int(rows[0][0])),
        # ---- Phân tích bổ sung (cá nhân)
        ("RFM: số khách đã mua & tổng chi tiêu", buyers_summary,
         "SELECT COUNT(*), SUM(monetary) FROM analytics.v_customer_rfm",
         lambda rows: [("Số khách đã mua", rows[0][0]), ("Tổng chi tiêu", int(rows[0][1] or 0))]),
        ("Tỉ lệ rời bỏ theo nguồn khách", churn_by_source,
         "SELECT customer_source, COUNT(*) FILTER (WHERE customer_status = 'churned')::numeric"
         " / NULLIF(COUNT(*) FILTER (WHERE customer_status IN ('customer', 'churned')), 0)"
         " FROM analytics.v_customers GROUP BY 1",
         lambda rows: sorted((src, round(float(rate), 4)) for src, rate in rows if rate is not None)),
        ("Cohort: số khách mua lần đầu theo tháng", cohort_sizes,
         "SELECT cohort_label, active_customers FROM analytics.v_cohort WHERE month_number = 0 ORDER BY 1",
         lambda rows: [(label, int(n)) for label, n in rows]),
    ]


def short(value, width=46):
    text = ", ".join(f"{a}: {b:,}" if isinstance(b, (int, Decimal)) else f"{a}: {b}" for a, b in value) \
        if isinstance(value, list) and value and isinstance(value[0], tuple) else (
            f"{value:,}" if isinstance(value, int) else str(value))
    return text if len(text) <= width else text[: width - 1] + "…"


class SupersetSQL:
    """Chạy SQL qua Superset SQL Lab bằng chính kết nối mà dashboard sử dụng (tài khoản superset_ro)."""

    def __init__(self):
        import httpx

        self.url = f"http://127.0.0.1:{os.getenv('SUPERSET_PORT', '8088')}"
        self.http = httpx.Client(base_url=self.url, timeout=60)
        login = self.http.post("/api/v1/security/login", json={
            "username": os.getenv("SUPERSET_ADMIN_USER", "admin"),
            "password": os.getenv("SUPERSET_ADMIN_PASSWORD", ""), "provider": "db", "refresh": True,
        })
        if login.status_code != 200:
            raise CommandError(f"Không đăng nhập được Superset tại {self.url}: {login.text[:200]}")
        self.http.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        self.http.headers["X-CSRFToken"] = self.http.get("/api/v1/security/csrf_token/").json()["result"]
        self.http.headers["Referer"] = self.url
        databases = self.http.get("/api/v1/database/", params={"q": "(page_size:100)"}).json()["result"]
        match = [d["id"] for d in databases if d["database_name"] == DATABASE_NAME]
        if not match:
            raise CommandError(f"Superset chưa có kết nối '{DATABASE_NAME}' – chạy superset/bootstrap_dashboard.py")
        self.database_id = match[0]

    def run(self, sql):
        response = self.http.post("/api/v1/sqllab/execute/", json={
            "database_id": self.database_id, "sql": sql, "schema": "analytics", "runAsync": False,
            "json": True, "queryLimit": 1000, "client_id": secrets.token_hex(5), "tab": "verify",
        })
        if response.status_code != 200:
            raise CommandError(f"Superset lỗi khi chạy SQL: {response.text[:300]}")
        body = response.json()
        names = [c["column_name"] for c in body["columns"]]
        return [tuple(row[n] for n in names) for row in body["data"]]


def normalise_superset(rows):
    """SQL Lab trả JSON: ngày thành chuỗi/epoch, số lớn thành float – đưa về kiểu Python như psycopg."""
    from datetime import date, datetime

    def fix(value):
        if isinstance(value, str) and len(value) >= 10 and value[4] == "-" and value[7] == "-":
            return date.fromisoformat(value[:10])
        if isinstance(value, (int, float)) and value > 10**11:  # epoch mili giây
            return datetime.utcfromtimestamp(value / 1000).date()
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    return [tuple(fix(v) for v in row) for row in rows]


class Command(BaseCommand):
    help = "Đối chiếu số liệu Wagtail (crm/analytics.py) với view analytics / Superset."

    def add_arguments(self, parser):
        parser.add_argument("--superset", action="store_true",
                            help="Chạy thêm các câu SQL qua Superset SQL Lab để đối chiếu.")

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Cần DB_ENGINE=postgres (view analytics chỉ có trên PostgreSQL).")
        superset = SupersetSQL() if options["superset"] else None

        failures = 0
        for name, wagtail_value, sql, normalise in build_checks():
            expected = wagtail_value()
            with connection.cursor() as cursor:
                cursor.execute(sql)
                from_view = normalise(cursor.fetchall())
            results = [("View PostgreSQL", from_view)]
            if superset:
                results.append(("Superset SQL Lab", normalise(normalise_superset(superset.run(sql)))))
            ok = all(value == expected for _, value in results)
            failures += not ok
            mark = self.style.SUCCESS("KHỚP") if ok else self.style.ERROR("LỆCH")
            self.stdout.write(f"[{mark}] {name}")
            self.stdout.write(f"        Wagtail /crm/     : {short(expected, 90)}")
            for label, value in results:
                self.stdout.write(f"        {label:<18}: {short(value, 90)}")

        sources = "Wagtail ↔ view PostgreSQL" + (" ↔ Superset" if superset else "")
        if failures:
            self.stdout.write(self.style.ERROR(f"\n{failures} chỉ số lệch ({sources})."))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f"\nTất cả chỉ số khớp ({sources})."))
        if superset:
            self.stdout.write(f"Dashboard: {superset.url}/superset/dashboard/smartcrm-th1/")
