import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm.models import AIReport, Customer, InteractionLog, Order, OrderItem, Product


class Command(BaseCommand):
    help = "Tạo dữ liệu mẫu cho CRM để kiểm thử AI/analytics (không cần dữ liệu thật)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Xoá dữ liệu cũ trước khi tạo mới.")
        parser.add_argument("--customers", type=int, default=10, help="Số lượng Customer cần tạo.")
        parser.add_argument("--orders", type=int, default=20, help="Số lượng Order cần tạo.")
        parser.add_argument("--interactions", type=int, default=30, help="Số lượng InteractionLog cần tạo.")
        parser.add_argument("--reports", type=int, default=5, help="Số lượng AIReport cần tạo.")

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options["reset"]
        customer_count = options["customers"]
        order_count = options["orders"]
        interaction_count = options["interactions"]
        report_count = options["reports"]

        if reset:
            self.stdout.write(self.style.WARNING("Đang xoá dữ liệu mock cũ..."))
            AIReport.objects.all().delete()
            InteractionLog.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()
            Customer.objects.all().delete()
            Product.objects.all().delete()

        existing_customers = Customer.objects.count()
        if existing_customers >= customer_count and not reset:
            self.stdout.write(self.style.WARNING(f"Đã có {existing_customers} Customer, bỏ qua tạo mới để tránh trùng lặp."))
            return

        self.stdout.write(self.style.NOTICE(f"Tạo {customer_count} khách hàng mẫu..."))
        customers = []
        first_names = [
            "An", "Bình", "Chi", "Dũng", "Hà", "Long", "Mai", "Nam", "Nhi", "Phúc",
            "Quân", "Sơn", "Thảo", "Uyên", "Vân", "Yến", "Khánh", "Minh", "Lan", "Hưng"
        ]
        last_names = [
            "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Hồ",
            "Ngô", "Dương", "Mai", "Tô", "Lý", "Tăng", "Cao", "Đinh", "Trương", "Phan"
        ]

        for i in range(customer_count):
            first = random.choice(first_names)
            last = random.choice(last_names)
            name = f"{first} {last}"
            email = f"customer{i + 1 + existing_customers}@example.com"
            status = random.choice([choice[0] for choice in Customer.Status.choices])
            source = random.choice([choice[0] for choice in Customer.Source.choices])
            customer = Customer.objects.create(
                name=name,
                email=email,
                phone=f"090{random.randint(1000000, 9999999)}",
                company=f"Công ty {i + 1}",
                status=status,
                source=source,
            )
            if hasattr(customer, "risk_score"):
                customer.risk_score = random.randint(0, 100)
                customer.save(update_fields=["risk_score"])
            customers.append(customer)

        self.stdout.write(self.style.NOTICE("Tạo sản phẩm mẫu..."))
        products = []
        product_specs = [
            ("P001", "Giải pháp CRM Pro", "gói", 1500000),
            ("P002", "Dịch vụ Tư vấn AI", "gói", 2200000),
            ("P003", "Bộ phân tích Funnel", "cái", 800000),
            ("P004", "Phần mềm quản lý khách hàng", "gói", 3000000),
            ("P005", "Phân tích rủi ro tín dụng", "gói", 2600000),
            ("P006", "Hỗ trợ triển khai dữ liệu", "gói", 1200000),
        ]
        for sku, name, unit, price in product_specs:
            product, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "unit": unit,
                    "price": Decimal(price),
                    "stock": random.randint(20, 100),
                    "min_stock": 10,
                    "track_stock": True,
                    "is_active": True,
                },
            )
            products.append(product)

        self.stdout.write(self.style.NOTICE(f"Tạo {order_count} đơn hàng mẫu..."))
        for i in range(order_count):
            customer = random.choice(customers)
            order = Order.objects.create(
                customer=customer,
                status=random.choice([choice[0] for choice in Order.Status.choices]),
                note=f"Đơn mẫu {i + 1}",
            )

            item_count = random.randint(1, 4)
            for _ in range(item_count):
                product = random.choice(products)
                quantity = random.randint(1, 5)
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    quantity=quantity,
                    unit_price=product.price,
                )

            # total_amount là property tính từ OrderItem, không gán được trực tiếp.
            # Sau khi chèn các OrderItem, `order.total_amount` sẽ tự tính đúng.

        self.stdout.write(self.style.NOTICE(f"Tạo {interaction_count} InteractionLog mẫu..."))
        channels = [choice[0] for choice in InteractionLog.Channel.choices]
        for i in range(interaction_count):
            customer = random.choice(customers)
            message = random.choice([
                "Khách hàng hỏi về giá và thời gian triển khai.",
                "Khách hàng hài lòng với quy trình và muốn nâng cấp gói.",
                "Khách hàng phàn nàn về thời gian phản hồi chậm.",
                "Khách hàng đang cân nhắc và cần thêm thông tin về tính năng.",
                "Khách hàng muốn gia hạn hợp đồng và hỏi thêm báo cáo AI.",
            ])
            InteractionLog.objects.create(
                customer=customer,
                channel=random.choice(channels),
                customer_message=message,
                ai_suggested_reply=f"Gợi ý phản hồi cho tương tác {i + 1}.",
                final_reply=f"Phản hồi mẫu {i + 1} cho khách hàng.",
                is_ai_generated=random.choice([True, False]),
            )

        self.stdout.write(self.style.NOTICE(f"Tạo {report_count} AIReport mẫu..."))
        for i in range(report_count):
            projected_revenue = Decimal(str(random.randint(1000000, 50000000)))
            content = (
                "Báo cáo phân tích AI: khách hàng có xu hướng tăng doanh thu trong 3 tháng tới "
                f"với mức dự báo khoảng {projected_revenue:,.0f} VNĐ."
            )
            report = AIReport.objects.create(
                content=content,
                stats={"predicted_revenue": str(projected_revenue), "confidence": round(random.uniform(0.75, 0.98), 3)},
                provider=random.choice(["gemini", "openai", "mock-ai"]),
                is_mock=True,
            )
            if hasattr(report, "predicted_revenue"):
                report.predicted_revenue = projected_revenue
                report.save(update_fields=["predicted_revenue"])

        self.stdout.write(self.style.SUCCESS("Hoàn tất: dữ liệu mock đã được tạo."))
