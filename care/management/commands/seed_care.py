"""Tạo dữ liệu mẫu cho phần Chăm sóc & Marketing (phiếu hỗ trợ, chiến dịch).

    python manage.py seed_care            # 30 phiếu hỗ trợ + 3 chiến dịch, dựa trên khách hàng đang có
    python manage.py seed_care --reset    # xoá dữ liệu mẫu của lệnh này rồi tạo lại

Chạy thủ công MỘT lần sau `migrate` và sau khi đã có khách hàng (seed_demo / seed_superset) –
không đặt trong luồng khởi động ứng dụng. Chỉ ghi vào các bảng của app ``care``.
Dữ liệu mẫu được đánh dấu bằng tiền tố "[Mẫu]" ở tiêu đề phiếu / tên chiến dịch.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from care.models import Campaign, CampaignMember, SupportTicket, TicketNote
from crm.models import Customer

MARK = "[Mẫu] "

# (loại, tiêu đề, nội dung, kết quả xử lý)
TICKETS = [
    ("technical", "Máy in hoá đơn không nhận lệnh in", "Máy in K80 bật nguồn bình thường nhưng bấm in không ra giấy.",
     "Hướng dẫn cài lại driver và chọn đúng cổng USB, in thử thành công."),
    ("technical", "Phần mềm báo lỗi khi xuất báo cáo Excel", "Xuất báo cáo doanh thu tháng thì báo lỗi và thoát.",
     "Cập nhật phiên bản mới, lỗi xuất file đã được khắc phục."),
    ("warranty", "Máy quét mã vạch chập chờn", "Mua được 2 tháng, máy quét lúc nhận lúc không.",
     "Đổi máy mới theo chính sách bảo hành 12 tháng."),
    ("question", "Hỏi cách thêm tài khoản nhân viên", "Cửa hàng mới tuyển thêm người, cần tạo tài khoản bán hàng.",
     "Đã gửi hướng dẫn và tạo giúp 2 tài khoản."),
    ("question", "Gia hạn gói phần mềm thế nào?", "Gói 12 tháng sắp hết hạn, muốn biết thủ tục gia hạn.",
     "Tư vấn gói gia hạn và gửi báo giá."),
    ("complaint", "Giao thiếu giấy in so với đơn", "Đặt 10 cuộn giấy K80 nhưng chỉ nhận được 8 cuộn.",
     "Xin lỗi khách và giao bù 2 cuộn trong ngày."),
    ("complaint", "Nhân viên hẹn gọi lại nhưng không gọi", "Đã chờ 2 ngày chưa thấy ai liên hệ tư vấn.",
     "Trưởng nhóm gọi xin lỗi, tư vấn trực tiếp và tặng 1 buổi đào tạo."),
    ("other", "Xin xuất lại hoá đơn VAT", "Cần xuất lại hoá đơn với tên công ty mới.", "Đã xuất lại và gửi qua email."),
]
NOTES = [
    "Đã gọi lại xác nhận thông tin với khách.",
    "Chuyển bộ phận kỹ thuật kiểm tra.",
    "Khách hẹn xử lý vào buổi chiều.",
]

# (tên, kênh, trạng thái, bắt đầu cách đây N ngày, kéo dài, ngân sách, trạng thái khách, nguồn khách, thông điệp)
CAMPAIGNS = [
    ("Ưu đãi Tết – gia hạn phần mềm", "email", "finished", 260, 30, 5_000_000, "customer", "",
     "Gia hạn trước Tết giảm 15% và tặng 1 tháng sử dụng."),
    ("Kích hoạt lại khách đã rời bỏ", "phone", "running", 20, 45, 3_000_000, "churned", "",
     "Gọi hỏi thăm, tặng mã giảm 20% cho đơn quay lại."),
    ("Chào mừng khách tiềm năng từ Facebook", "zalo", "draft", 0, 30, 2_000_000, "lead", "facebook",
     "Gửi bộ tài liệu giới thiệu và mời dùng thử 14 ngày."),
]


class Command(BaseCommand):
    help = "Tạo dữ liệu mẫu cho Phiếu hỗ trợ và Chiến dịch marketing."

    def add_arguments(self, parser):
        parser.add_argument("--tickets", type=int, default=30, help="Số phiếu hỗ trợ mẫu (mặc định 30).")
        parser.add_argument("--seed", type=int, default=2026, help="Hạt giống ngẫu nhiên (mặc định 2026).")
        parser.add_argument("--reset", action="store_true", help="Xoá dữ liệu mẫu của lệnh này trước khi tạo lại.")

    @transaction.atomic
    def handle(self, *args, **options):
        tickets = SupportTicket.objects.filter(subject__startswith=MARK)
        campaigns = Campaign.objects.filter(name__startswith=MARK)
        if options["reset"]:
            counts = (tickets.count(), campaigns.count())
            tickets.delete()
            campaigns.delete()
            self.stdout.write(self.style.WARNING(f"Đã xoá {counts[0]} phiếu hỗ trợ và {counts[1]} chiến dịch mẫu."))
        elif tickets.exists() or campaigns.exists():
            raise CommandError("Đã có dữ liệu mẫu. Thêm --reset để xoá và tạo lại.")

        customers = list(Customer.objects.select_related("assigned_staff").order_by("pk"))
        if not customers:
            raise CommandError("Chưa có khách hàng. Chạy seed_demo hoặc seed_superset trước.")

        self.rng = random.Random(options["seed"])
        self.now = timezone.now()
        self.create_tickets(customers, options["tickets"])
        member_count = self.create_campaigns()
        self.stdout.write(self.style.SUCCESS(
            f"Đã tạo {options['tickets']} phiếu hỗ trợ ({SupportTicket.open_overdue().count()} phiếu đang quá hạn) "
            f"và {len(CAMPAIGNS)} chiến dịch với {member_count} lượt khách."
        ))

    def create_tickets(self, customers, count):
        rng = self.rng
        for _ in range(count):
            customer = rng.choice(customers)
            category, subject, description, resolution = rng.choice(TICKETS)
            # Khoảng 1/3 phiếu nằm trong tuần này để có phiếu Mới / Đang xử lý
            days = rng.randint(0, 6) if rng.random() < 0.35 else rng.randint(7, 90)
            created = self.now - timedelta(days=days, hours=rng.randint(1, 9))
            priority = rng.choices(["high", "medium", "low"], weights=[2, 5, 3])[0]
            sla = SupportTicket.SLA_HOURS[priority]
            # Phiếu cũ đa số đã xong, phiếu mới còn đang xử lý
            if (self.now - created).days > 7:
                status = rng.choices(["closed", "resolved", "waiting"], weights=[60, 30, 10])[0]
            else:
                status = rng.choices(["new", "in_progress", "waiting", "resolved"], weights=[30, 35, 15, 20])[0]
            done = status in SupportTicket.DONE_STATUSES
            orders = list(customer.orders.order_by("pk")) if rng.random() < 0.4 else []
            ticket = SupportTicket(
                customer=customer,
                order=rng.choice(orders) if orders else None,
                subject=MARK + subject,
                description=description,
                category=category,
                priority=priority,
                status=status,
                channel=rng.choice(["phone", "email", "chat", "in_person"]),
                assigned_staff=customer.assigned_staff,
                due_at=created + timedelta(hours=sla),
                resolution=resolution if done else "",
                satisfaction=rng.choices([5, 4, 3, 2, 1], weights=[40, 30, 15, 10, 5])[0] if done else None,
                notes=[TicketNote(content=rng.choice(NOTES)) for _ in range(rng.randint(0, 2))],
            )
            ticket.save()
            # Lùi ngày về quá khứ; phiếu đã xong thì khoảng 75% đúng hạn
            resolved = None
            if done:
                on_time = rng.random() < 0.75
                resolved = created + timedelta(hours=sla * (rng.uniform(0.2, 0.9) if on_time else rng.uniform(1.2, 3)))
                resolved = min(resolved, self.now)
            SupportTicket.objects.filter(pk=ticket.pk).update(created_at=created, resolved_at=resolved)

    def create_campaigns(self):
        rng = self.rng
        total = 0
        for name, channel, status, days_ago, length, budget, target_status, target_source, message in CAMPAIGNS:
            start = (self.now - timedelta(days=days_ago)).date()
            # Tạo ở Bản nháp để hệ thống tự lập danh sách khách theo điều kiện, rồi mới chuyển trạng thái
            campaign = Campaign.objects.create(
                name=MARK + name, channel=channel, start_date=start, end_date=start + timedelta(days=length),
                budget=Decimal(budget), target_status=target_status, target_source=target_source, message=message,
            )
            total += campaign.member_count
            if status == Campaign.Status.DRAFT:
                continue
            campaign.status = status
            campaign.save()
            weights = [10, 35, 25, 20, 10] if status == Campaign.Status.FINISHED else [45, 30, 12, 5, 8]
            contacted = self.now - timedelta(days=max(days_ago - 2, 0))
            for member in campaign.members.all():
                member.response = rng.choices(
                    ["pending", "sent", "responded", "converted", "declined"], weights=weights
                )[0]
                member.contacted_at = contacted if member.response != CampaignMember.Response.PENDING else None
                member.save()
        return total
