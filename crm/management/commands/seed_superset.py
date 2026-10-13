"""Sinh bộ dữ liệu mẫu lớn (khách hàng, đơn hàng, doanh thu) để phân tích bằng Apache Superset – TH1.

    python manage.py seed_superset                         # 150 khách, 18 tháng, seed = TH1_SEED trong .env
    python manage.py seed_superset --customers 300 --months 24 --seed 7
    python manage.py seed_superset --reset --analyze       # xoá dữ liệu do lệnh này tạo rồi sinh lại

Chạy thủ công MỘT lần sau `migrate` – không đặt trong luồng khởi động ứng dụng.
Dữ liệu ngẫu nhiên nhưng tái lập được: cùng --seed luôn ra cùng một bộ số liệu.
Khách hàng do lệnh này tạo có email @sample.smartcrm.vn (tách biệt với dữ liệu của seed_demo).
"""

import os
import random
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from crm.models import Customer, InteractionLog, Order, OrderItem, Product

from .seed_demo import PRODUCTS

SAMPLE_DOMAIN = "sample.smartcrm.vn"

# Nhân viên kinh doanh mẫu (không đăng nhập được – chỉ để phân tích doanh thu theo nhân viên)
SALES_STAFF = [
    ("sale.hoa", "Hoa", "Nguyễn Thị"),
    ("sale.minh", "Minh", "Trần Quang"),
    ("sale.tuan", "Tuấn", "Lê Anh"),
]

HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương"]
DEM = ["Văn", "Thị", "Minh", "Thu", "Hoàng", "Ngọc", "Quốc", "Thanh", "Gia", "Đức", "Hải", "Phương"]
TEN = ["An", "Bình", "Châu", "Dũng", "Giang", "Hà", "Hải", "Hạnh", "Hiếu", "Hoa", "Hùng", "Khánh", "Lan", "Linh",
       "Long", "Mai", "Nam", "Nga", "Nhung", "Phong", "Phúc", "Quân", "Sơn", "Tâm", "Thảo", "Trang", "Tú", "Vy", "Yến"]
COMPANY_KIND = ["Công ty TNHH", "Công ty CP", "Cửa hàng", "Nhà thuốc", "Quán cà phê", "Siêu thị mini", "Spa"]
COMPANY_NAME = ["Minh Phát", "An Khang", "Hưng Thịnh", "Phú Quý", "Sao Mai", "Hoa Sen", "Đông Á", "Việt Tiến",
                "Thành Công", "Bình Minh", "Kim Long", "Tân Phú", "Hồng Hà", "Nam Việt", "Hải Âu"]

# Nguồn khách: (tỉ trọng khách mới, mức độ mua lặp lại – khách giới thiệu mua nhiều nhất)
SOURCES = {"website": (40, 2.2), "facebook": (30, 1.8), "referral": (18, 3.0), "other": (12, 1.2)}

# Giỏ hàng theo nhóm khách: danh sách (SKU, trọng số, SL tối thiểu, SL tối đa)
BASKETS = {
    "business": [
        ("CRM-DN-12", 3, 1, 1), ("PM-BH-12", 4, 1, 1), ("DV-TK", 5, 2, 10), ("DV-DT", 3, 1, 3),
        ("DV-HT", 4, 1, 1), ("DV-WEB", 2, 1, 1), ("DV-TD", 2, 1, 1), ("TB-POS", 1, 1, 2),
    ],
    "shop": [
        ("PM-BH-06", 4, 1, 1), ("PM-BH-12", 2, 1, 1), ("TB-K80", 8, 1, 6), ("TB-MIN", 3, 1, 2),
        ("TB-QR", 4, 1, 2), ("TB-KET", 2, 1, 1), ("TB-POS", 2, 1, 1), ("DV-HT", 2, 1, 1),
    ],
}

# Hệ số mùa vụ theo tháng: mua sắm tăng dịp Tết (T1–T2) và cuối năm, chững lại giữa năm
SEASONALITY = {1: 1.5, 2: 1.2, 3: 0.9, 4: 0.9, 5: 1.0, 6: 0.8, 7: 0.8, 8: 0.9, 9: 1.0, 10: 1.1, 11: 1.25, 12: 1.4}

MESSAGES = {
    "email": ["Cho mình xin báo giá gói phần mềm bán hàng.", "Hoá đơn tháng này đã được xuất chưa?",
              "Bên mình muốn gia hạn thêm 12 tháng.", "Phần mềm báo lỗi khi xuất báo cáo Excel."],
    "phone": ["Anh muốn đặt thêm giấy in K80.", "Máy in hoá đơn không nhận lệnh in.",
              "Chị cần tư vấn thêm tài khoản cho nhân viên mới."],
    "chat": ["Shop ơi còn máy quét mã vạch không?", "Có hỗ trợ lắp đặt tận nơi không ạ?",
             "Gói 6 tháng và 12 tháng khác nhau thế nào?", "Cảm ơn shop, dùng ổn lắm!"],
    "in_person": ["Hẹn gặp để demo phần mềm cho ban giám đốc.", "Khách ghé cửa hàng xem máy POS."],
}
REPLY = "Dạ em đã ghi nhận, bộ phận phụ trách sẽ liên hệ lại anh/chị trong hôm nay ạ."


class Command(BaseCommand):
    help = "Sinh dữ liệu mẫu lớn (khách hàng, đơn hàng, doanh thu) cho phân tích Apache Superset."

    def add_arguments(self, parser):
        parser.add_argument("--customers", type=int, default=150, help="Số khách hàng mẫu (mặc định 150).")
        parser.add_argument("--months", type=int, default=18, help="Số tháng dữ liệu tính đến hôm nay (mặc định 18).")
        parser.add_argument(
            "--seed", type=int, default=int(os.getenv("TH1_SEED") or 2026),
            help="Hạt giống ngẫu nhiên – cùng giá trị cho cùng dữ liệu (mặc định TH1_SEED trong .env, không có thì 2026).",
        )
        parser.add_argument("--reset", action="store_true", help="Xoá dữ liệu do lệnh này tạo trước khi sinh lại.")
        parser.add_argument(
            "--analyze", action="store_true",
            help="Điền kết quả phân loại AI (luôn dùng MOCK, không gọi AI thật) cho khách mẫu.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["customers"] < 1 or options["months"] < 1:
            raise CommandError("--customers và --months phải lớn hơn 0.")

        samples = Customer.objects.filter(email__endswith=f"@{SAMPLE_DOMAIN}")
        if options["reset"]:
            count = samples.count()
            samples.delete()  # đơn hàng, tương tác bị xoá theo (CASCADE), hàng được hoàn về kho
            self.stdout.write(self.style.WARNING(f"Đã xoá {count} khách hàng mẫu (@{SAMPLE_DOMAIN}) cùng dữ liệu liên quan."))
        elif samples.exists():
            raise CommandError(f"Đã có dữ liệu @{SAMPLE_DOMAIN}. Thêm --reset để xoá và sinh lại.")

        self.rng = random.Random(options["seed"])
        self.now = timezone.now()
        self.start = self.now - timedelta(days=round(options["months"] * 30.4))
        self.products = self.ensure_products()
        staff = self.ensure_staff()

        plans = [self.plan_customer(i, staff) for i in range(1, options["customers"] + 1)]
        self.plan_orders(plans)
        for plan in plans:
            plan["status"] = self.customer_status(plan["orders"], plan["interactions"])
        self.prepare_stock(plans)

        customers = self.create_customers(plans)
        order_count = self.create_orders(plans, customers)
        interaction_count = self.create_interactions(plans, customers)

        analyzed = 0
        if options["analyze"]:
            from crm.services.ai_service import GeminiCRMService

            for customer in customers.values():
                GeminiCRMService.save_analysis(
                    customer, GeminiCRMService._mock_analysis(customer), "AI Gemini (chế độ mô phỏng)"
                )
                analyzed += 1

        self.stdout.write(self.style.SUCCESS(
            f"Đã sinh {len(customers)} khách hàng, {order_count} đơn hàng, {interaction_count} tương tác "
            f"trong {options['months']} tháng (seed={options['seed']}); phân loại AI (mô phỏng) {analyzed} khách."
        ))
        self.stdout.write(
            f"Tổng hiện có: {Customer.objects.count()} khách hàng, {Order.objects.count()} đơn hàng, "
            f"{Product.objects.count()} sản phẩm ({Product.low_stock().count()} sắp hết hàng)."
        )

    # ------------------------------------------------------------------ chuẩn bị
    def ensure_products(self):
        products = {}
        for sku, name, unit, price, track_stock, stock, min_stock in PRODUCTS:
            products[sku], _ = Product.objects.get_or_create(sku=sku, defaults={
                "name": name, "unit": unit, "price": Decimal(price),
                "track_stock": track_stock, "stock": stock, "min_stock": min_stock,
            })
        return products

    def ensure_staff(self):
        User = get_user_model()
        staff = []
        for username, first_name, last_name in SALES_STAFF:
            user, created = User.objects.get_or_create(
                username=username, defaults={"first_name": first_name, "last_name": last_name},
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            staff.append(user)
        return staff

    def working_hours(self, moment):
        return timezone.localtime(moment).replace(hour=self.rng.randint(8, 20), minute=self.rng.randint(0, 59))

    def random_moment(self, after):
        """Thời điểm ngẫu nhiên từ ``after`` tới nay, trong giờ làm việc."""
        return self.working_hours(after + (self.now - after) * self.rng.random())

    def month_ranges(self):
        """Các cặp (đầu tháng, cuối tháng) theo giờ Việt Nam, từ tháng bắt đầu tới hôm nay."""
        cursor = timezone.localtime(self.start).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        while cursor < self.now:
            following = (cursor + timedelta(days=32)).replace(day=1)
            yield max(cursor, self.start), min(following, self.now)
            cursor = following

    # ------------------------------------------------------------------ lập kế hoạch
    def plan_customer(self, index, staff):
        rng = self.rng
        source = rng.choices(list(SOURCES), weights=[w for w, _ in SOURCES.values()])[0]
        # Khách mới tăng dần theo thời gian (doanh nghiệp đang tăng trưởng)
        created = self.working_hours(self.start + (self.now - self.start) * (rng.random() ** 0.85))
        has_company = rng.random() < 0.45
        # ~18% chỉ hỏi thăm, không mua; ~30% ngừng mua sau một thời gian (rời bỏ)
        churn_at = created + (self.now - created) * rng.uniform(0.3, 0.9) if rng.random() < 0.3 else None
        return {
            "email": f"kh{index:04d}@{SAMPLE_DOMAIN}",
            "name": f"{rng.choice(HO)} {rng.choice(DEM)} {rng.choice(TEN)}",
            "phone": f"09{rng.randint(10_000_000, 99_999_999)}",
            "company": f"{rng.choice(COMPANY_KIND)} {rng.choice(COMPANY_NAME)}" if has_company else "",
            "basket": "business" if has_company else "shop",
            "source": source,
            "created": created,
            "buyer": rng.random() >= 0.18,
            "churn_at": churn_at,
            "staff": rng.choice(staff),
            "orders": [],
            "interactions": [
                (channel, self.random_moment(created))
                for channel in rng.choices(list(MESSAGES), weights=[4, 3, 4, 1], k=rng.randint(0, 4))
            ],
        }

    def plan_orders(self, plans):
        """Số đơn mỗi tháng = nền × mùa vụ × tăng trưởng; mỗi đơn gán cho một khách đang hoạt động."""
        rng = self.rng
        ranges = list(self.month_ranges())
        base = len(plans) * 0.16
        for index, (begin, end) in enumerate(ranges):
            growth = 0.7 + 0.6 * index / max(len(ranges) - 1, 1)
            share = (end - begin) / timedelta(days=30.4)  # tháng hiện tại mới chạy được một phần
            expected = base * SEASONALITY[begin.month] * growth * share
            for _ in range(max(0, round(rng.gauss(expected, expected ** 0.5)))):
                date = self.working_hours(begin + (end - begin) * rng.random())
                if date > self.now:
                    date = self.now
                active = [
                    p for p in plans
                    if p["buyer"] and p["created"] < date and (p["churn_at"] is None or date < p["churn_at"])
                ]
                if not active:
                    continue
                plan = rng.choices(active, weights=[SOURCES[p["source"]][1] for p in active])[0]
                plan["orders"].append(self.plan_order(date, plan["basket"]))
        for plan in plans:
            plan["orders"].sort(key=lambda o: o["date"])

    def plan_order(self, date, basket_name):
        rng = self.rng
        age = (self.now - date).days
        if age > 30:
            status = rng.choices(["completed", "cancelled"], weights=[88, 12])[0]
        elif age > 7:
            status = rng.choices(["completed", "processing", "cancelled", "new"], weights=[60, 25, 8, 7])[0]
        else:
            status = rng.choices(["new", "processing", "completed"], weights=[50, 35, 15])[0]
        basket = BASKETS[basket_name]
        picked = rng.sample(basket, k=rng.choices([1, 2, 3], weights=[55, 30, 15])[0])
        items = [(sku, rng.randint(low, high)) for sku, _, low, high in picked]
        return {"date": date, "status": status, "items": items}

    def customer_status(self, orders, interactions):
        completed = [o for o in orders if o["status"] == "completed"]
        if completed:
            last = max(o["date"] for o in orders)
            return "churned" if (self.now - last).days > 180 else "customer"
        return "caring" if orders or interactions else "lead"

    def prepare_stock(self, plans):
        """Đặt tồn kho đủ cho mọi đơn Hoàn thành; phần còn lại ngẫu nhiên nên có sản phẩm sắp hết hàng."""
        need = defaultdict(int)
        for plan in plans:
            for order in plan["orders"]:
                if order["status"] == "completed":
                    for sku, quantity in order["items"]:
                        need[sku] += quantity
        tracked = sorted((p for p in self.products.values() if p.track_stock), key=lambda p: p.sku)
        low = {p.sku for p in self.rng.sample(tracked, k=round(len(tracked) * 0.4))}
        for product in tracked:
            remaining = (
                self.rng.randint(0, product.min_stock) if product.sku in low
                else self.rng.randint(product.min_stock + 1, product.min_stock * 3 + 2)
            )
            product.stock = need[product.sku] + remaining
            product.save(update_fields=["stock"])

    # ------------------------------------------------------------------ ghi CSDL
    def create_customers(self, plans):
        customers = {}
        for plan in plans:
            customer = Customer.objects.create(
                email=plan["email"], name=plan["name"], phone=plan["phone"], company=plan["company"],
                status=plan["status"], source=plan["source"], assigned_staff=plan["staff"],
            )
            Customer.objects.filter(pk=customer.pk).update(created_at=plan["created"])
            customers[plan["email"]] = customer
        return customers

    def create_orders(self, plans, customers):
        # Tạo theo thứ tự thời gian để kho bị trừ đúng như thực tế
        pending = sorted(
            ((order, customers[plan["email"]]) for plan in plans for order in plan["orders"]),
            key=lambda pair: pair[0]["date"],
        )
        for order_plan, customer in pending:
            order = Order(
                customer=customer,
                status=order_plan["status"],
                code=Order.generate_code(order_plan["date"].date()),
                items=[OrderItem(product=self.products[sku], quantity=qty) for sku, qty in order_plan["items"]],
            )
            order.save()  # lưu đơn + dòng sản phẩm, trừ kho nếu Hoàn thành
            Order.objects.filter(pk=order.pk).update(created_at=order_plan["date"])
        return len(pending)

    def create_interactions(self, plans, customers):
        logs = []
        for plan in plans:
            for channel, moment in plan["interactions"]:
                answered = self.rng.random() < 0.8
                used_ai = answered and self.rng.random() < 0.4
                logs.append(InteractionLog(
                    customer=customers[plan["email"]],
                    channel=channel,
                    customer_message=self.rng.choice(MESSAGES[channel]),
                    ai_suggested_reply=REPLY if used_ai else "",
                    final_reply=REPLY if answered else "",
                    is_ai_generated=used_ai,
                    staff=plan["staff"] if answered else None,
                ))
        InteractionLog.objects.bulk_create(logs)
        moments = [moment for plan in plans for _, moment in plan["interactions"]]
        for log, moment in zip(logs, moments):
            InteractionLog.objects.filter(pk=log.pk).update(created_at=moment)
        return len(logs)
