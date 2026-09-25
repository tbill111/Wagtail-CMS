"""Tạo dữ liệu mẫu cho SmartCRM.

    python manage.py seed_demo          # chạy lại nhiều lần không bị trùng
    python manage.py seed_demo --reset  # xoá dữ liệu mẫu cũ rồi tạo lại
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm.models import Customer, InteractionLog, Order, OrderItem

DEMO_DOMAIN = "demo.smartcrm.vn"

# (tên, email-prefix, sđt, công ty, trạng thái, nguồn, số ngày trước)
CUSTOMERS = [
    ("Nguyễn Văn An", "an.nguyen", "0901234567", "Công ty TNHH Minh Phát", "customer", "website", 120),
    ("Trần Thị Bình", "binh.tran", "0912345678", "", "customer", "facebook", 95),
    ("Lê Hoàng Cường", "cuong.le", "0987654321", "Cường Lê Studio", "caring", "referral", 40),
    ("Phạm Thu Dung", "dung.pham", "0934567890", "", "lead", "website", 6),
    ("Hoàng Minh Đức", "duc.hoang", "0978123456", "Đức Minh Logistics", "customer", "referral", 200),
    ("Vũ Ngọc Hà", "ha.vu", "0965432109", "", "churned", "facebook", 300),
    ("Đặng Quốc Huy", "huy.dang", "0923456781", "Huy Đặng Coffee", "caring", "other", 25),
    ("Bùi Thanh Lan", "lan.bui", "0945678123", "", "lead", "facebook", 3),
    ("Đỗ Mạnh Khang", "khang.do", "0356789012", "Khang Thịnh JSC", "customer", "website", 60),
    ("Ngô Phương Linh", "linh.ngo", "0389012345", "", "churned", "other", 150),
]

# email-prefix -> danh sách đơn: (trạng thái, số ngày trước, [(sản phẩm, SL, đơn giá)], ghi chú)
ORDERS = {
    "an.nguyen": [
        ("completed", 110, [("Gói phần mềm quản lý bán hàng (12 tháng)", 1, 4800000), ("Đào tạo sử dụng tại chỗ", 1, 1500000)], "Khách thanh toán chuyển khoản"),
        ("processing", 5, [("Gia hạn gói hỗ trợ kỹ thuật", 1, 1200000)], ""),
    ],
    "binh.tran": [
        ("completed", 90, [("Máy in hoá đơn nhiệt", 2, 1350000), ("Giấy in K80 (thùng)", 3, 320000)], ""),
        ("completed", 30, [("Giấy in K80 (thùng)", 5, 320000)], "Giao tại cửa hàng"),
    ],
    "cuong.le": [
        ("new", 2, [("Thiết kế website giới thiệu", 1, 9500000)], "Chờ khách duyệt báo giá"),
    ],
    "duc.hoang": [
        ("completed", 180, [("Gói CRM doanh nghiệp (12 tháng)", 1, 12000000)], ""),
        ("completed", 45, [("Thêm 5 tài khoản người dùng", 5, 600000)], ""),
        ("cancelled", 20, [("Tích hợp tổng đài", 1, 3500000)], "Khách đổi kế hoạch"),
    ],
    "ha.vu": [
        ("completed", 280, [("Gói phần mềm quản lý bán hàng (6 tháng)", 1, 2600000)], ""),
    ],
    "huy.dang": [
        ("processing", 10, [("Máy bán hàng POS cảm ứng", 1, 7900000), ("Két đựng tiền", 1, 850000)], "Hẹn lắp đặt cuối tuần"),
    ],
    "khang.do": [
        ("completed", 50, [("Gói CRM doanh nghiệp (12 tháng)", 1, 12000000), ("Đào tạo sử dụng tại chỗ", 2, 1500000)], ""),
        ("new", 1, [("Thêm 3 tài khoản người dùng", 3, 600000)], ""),
    ],
}

# email-prefix -> danh sách tương tác: (kênh, số ngày trước, tin nhắn khách, phản hồi, có dùng AI)
INTERACTIONS = {
    "an.nguyen": [
        ("email", 100, "Chào shop, phần mềm có xuất được báo cáo doanh thu theo tháng không?", "Dạ chào anh An, phần mềm có sẵn báo cáo doanh thu theo ngày/tháng/năm và xuất ra Excel ạ.", False),
        ("phone", 6, "Anh muốn gia hạn thêm gói hỗ trợ kỹ thuật, bên em báo giá giúp anh.", "Em đã tạo đơn gia hạn 1.200.000 ₫, bộ phận kế toán sẽ gửi hoá đơn cho anh trong hôm nay.", False),
        ("email", 1, "Đơn gia hạn của anh đang xử lý tới đâu rồi em?", "", False),
    ],
    "binh.tran": [
        ("chat", 88, "Máy in hoá đơn in bị mờ, chị phải làm sao?", "Chị vui lòng vệ sinh đầu in bằng cồn và kiểm tra lại cuộn giấy đúng mặt nhiệt giúp em nhé.", False),
        ("chat", 29, "Chị đặt thêm 5 thùng giấy K80, giao ở cửa hàng như lần trước nhé.", "Dạ em đã lên đơn, dự kiến giao trong 2 ngày ạ.", True),
    ],
    "cuong.le": [
        ("email", 38, "Mình cần làm website giới thiệu studio, bên bạn có mẫu nào tham khảo không?", "Chào anh Cường, em gửi anh 3 mẫu website studio trong file đính kèm ạ.", False),
        ("email", 2, "Mình đã xem báo giá thiết kế website, có thể giảm chi phí được không?", "", False),
    ],
    "duc.hoang": [
        ("in_person", 170, "Công ty cần triển khai CRM cho phòng kinh doanh 15 người.", "Bên em đã tư vấn gói CRM doanh nghiệp và lịch đào tạo cho phòng kinh doanh.", False),
        ("email", 21, "Tạm thời công ty chưa cần tích hợp tổng đài, huỷ giúp anh đơn đó.", "Dạ em đã huỷ đơn tích hợp tổng đài theo yêu cầu của anh.", True),
    ],
    "ha.vu": [
        ("email", 260, "Báo cáo tồn kho hiển thị sai số lượng, em kiểm tra giúp chị.", "Dạ lỗi do chưa đồng bộ phiếu nhập, em đã xử lý xong, chị tải lại trang giúp em ạ.", False),
        ("phone", 200, "Phần mềm dùng hơi khó, chị chưa muốn gia hạn.", "Dạ em ghi nhận góp ý của chị, em xin gửi tài liệu hướng dẫn chi tiết hơn ạ.", False),
    ],
    "huy.dang": [
        ("chat", 12, "Quán cà phê của anh cần một bộ máy bán hàng, có lắp đặt tận nơi không?", "Dạ bên em có lắp đặt tận nơi miễn phí trong nội thành ạ.", False),
        ("phone", 4, "Cuối tuần này bên em qua lắp máy POS được không?", "Dạ kỹ thuật viên sẽ qua lắp vào sáng thứ Bảy, em sẽ gọi trước 30 phút ạ.", True),
        ("chat", 0, "Máy POS có kết nối được với máy in bếp không em?", "", False),
    ],
    "dung.pham": [
        ("chat", 6, "Mình thấy quảng cáo SmartCRM trên website, cho mình xin tài liệu giới thiệu.", "Dạ em gửi chị tài liệu giới thiệu qua email ạ.", True),
        ("email", 5, "Chào bạn, mình đang tìm phần mềm quản lý cho cửa hàng mỹ phẩm nhỏ, có dùng thử miễn phí không?", "", False),
    ],
    "lan.bui": [
        ("chat", 2, "Shop ơi, gói phần mềm 6 tháng giá bao nhiêu vậy?", "", False),
    ],
    "khang.do": [
        ("email", 48, "Cảm ơn team đã đào tạo rất nhiệt tình!", "Cảm ơn anh Khang, bên em luôn sẵn sàng hỗ trợ ạ.", False),
        ("email", 1, "Bên anh vừa đặt thêm 3 tài khoản, khi nào thì kích hoạt được?", "", False),
    ],
    "linh.ngo": [
        ("phone", 140, "Chị chuyển sang dùng phần mềm khác rồi, cảm ơn em.", "Dạ em cảm ơn chị đã đồng hành, mong có dịp phục vụ chị lần sau ạ.", False),
    ],
}


class Command(BaseCommand):
    help = "Tạo dữ liệu mẫu (khách hàng, đơn hàng, tương tác) cho SmartCRM."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Xoá dữ liệu mẫu cũ trước khi tạo lại.")

    @transaction.atomic
    def handle(self, *args, **options):
        demo_customers = Customer.objects.filter(email__endswith=f"@{DEMO_DOMAIN}")
        if options["reset"]:
            count = demo_customers.count()
            demo_customers.delete()  # đơn hàng, tương tác bị xoá theo (CASCADE)
            self.stdout.write(self.style.WARNING(f"Đã xoá {count} khách hàng mẫu cùng dữ liệu liên quan."))

        User = get_user_model()
        staff = User.objects.filter(is_staff=True).order_by("id").first()
        now = timezone.now()
        created = {"customers": 0, "orders": 0, "interactions": 0}

        for name, prefix, phone, company, status, source, days_ago in CUSTOMERS:
            customer, is_new = Customer.objects.get_or_create(
                email=f"{prefix}@{DEMO_DOMAIN}",
                defaults={
                    "name": name,
                    "phone": phone,
                    "company": company,
                    "status": status,
                    "source": source,
                    "assigned_staff": staff,
                },
            )
            if is_new:
                created["customers"] += 1
                Customer.objects.filter(pk=customer.pk).update(created_at=now - timedelta(days=days_ago))

            if not customer.orders.exists():
                for order_status, order_days, items, note in ORDERS.get(prefix, []):
                    order_date = now - timedelta(days=order_days)
                    order = Order.objects.create(
                        customer=customer,
                        status=order_status,
                        note=note,
                        code=Order.generate_code(timezone.localdate(order_date)),
                    )
                    for product_name, quantity, unit_price in items:
                        OrderItem.objects.create(
                            order=order,
                            product_name=product_name,
                            quantity=quantity,
                            unit_price=Decimal(unit_price),
                        )
                    Order.objects.filter(pk=order.pk).update(created_at=order_date)
                    created["orders"] += 1

            if not customer.interactions.exists():
                for channel, int_days, message, reply, used_ai in INTERACTIONS.get(prefix, []):
                    log = InteractionLog.objects.create(
                        customer=customer,
                        channel=channel,
                        customer_message=message,
                        ai_suggested_reply=reply if used_ai else "",
                        final_reply=reply,
                        is_ai_generated=used_ai,
                        staff=staff if reply else None,
                    )
                    InteractionLog.objects.filter(pk=log.pk).update(
                        created_at=now - timedelta(days=int_days, hours=len(message) % 9)
                    )
                    created["interactions"] += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Hoàn tất dữ liệu mẫu: thêm mới {customers} khách hàng, {orders} đơn hàng, "
                "{interactions} tương tác.".format(**created)
            )
        )
        self.stdout.write(
            f"Tổng hiện có: {Customer.objects.count()} khách hàng, {Order.objects.count()} đơn hàng, "
            f"{InteractionLog.objects.count()} tương tác."
        )
