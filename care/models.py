"""Chăm sóc sau bán (phiếu hỗ trợ) và Marketing (chiến dịch) – phần mở rộng của SmartCRM.

App tách riêng khỏi ``crm``: chỉ tham chiếu tới Customer / Order, không sửa bảng nào của ``crm``.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.models import Orderable

from crm.models import Customer, InteractionLog, Order, OrderItem


def next_daily_code(model, prefix, date=None):
    """Sinh mã dạng <PREFIX>-YYYYMMDD-0001, tăng dần theo ngày (cùng quy ước với mã đơn hàng)."""
    date = date or timezone.localdate()
    prefix = f"{prefix}-{date:%Y%m%d}-"
    last_code = (
        model.objects.filter(code__startswith=prefix).order_by("-code").values_list("code", flat=True).first()
    )
    next_number = int(last_code.rsplit("-", 1)[1]) + 1 if last_code else 1
    return f"{prefix}{next_number:04d}"


# ====================================================================== Chăm sóc / hỗ trợ
class SupportTicket(ClusterableModel):
    class Category(models.TextChoices):
        QUESTION = "question", "Hỏi đáp"
        TECHNICAL = "technical", "Lỗi kỹ thuật"
        WARRANTY = "warranty", "Bảo hành / đổi trả"
        COMPLAINT = "complaint", "Khiếu nại"
        OTHER = "other", "Khác"

    class Status(models.TextChoices):
        NEW = "new", "Mới"
        IN_PROGRESS = "in_progress", "Đang xử lý"
        WAITING = "waiting", "Chờ khách phản hồi"
        RESOLVED = "resolved", "Đã giải quyết"
        CLOSED = "closed", "Đã đóng"

    class Satisfaction(models.IntegerChoices):
        VERY_BAD = 1, "1 – Rất không hài lòng"
        BAD = 2, "2 – Không hài lòng"
        NORMAL = 3, "3 – Bình thường"
        GOOD = 4, "4 – Hài lòng"
        VERY_GOOD = 5, "5 – Rất hài lòng"

    DONE_STATUSES = (Status.RESOLVED, Status.CLOSED)
    # Thời hạn xử lý (giờ) theo mức ưu tiên
    SLA_HOURS = {Customer.Priority.HIGH: 4, Customer.Priority.MEDIUM: 24, Customer.Priority.LOW: 72}

    code = models.CharField("Mã phiếu", max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        Customer, verbose_name="Khách hàng", on_delete=models.CASCADE, related_name="tickets"
    )
    order = models.ForeignKey(
        Order,
        verbose_name="Đơn hàng liên quan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets",
    )
    subject = models.CharField("Tiêu đề", max_length=200)
    description = models.TextField("Nội dung yêu cầu")
    category = models.CharField(
        "Loại yêu cầu", max_length=20, choices=Category.choices, default=Category.QUESTION
    )
    priority = models.CharField(
        "Mức ưu tiên", max_length=20, choices=Customer.Priority.choices, default=Customer.Priority.MEDIUM
    )
    status = models.CharField("Trạng thái", max_length=20, choices=Status.choices, default=Status.NEW)
    channel = models.CharField(
        "Kênh tiếp nhận", max_length=20, choices=InteractionLog.Channel.choices,
        default=InteractionLog.Channel.PHONE,
    )
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Nhân viên xử lý",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
    )
    due_at = models.DateTimeField(
        "Hạn xử lý", null=True, blank=True,
        help_text="Bỏ trống để tự tính theo mức ưu tiên: Cao 4 giờ, Trung bình 24 giờ, Thấp 72 giờ.",
    )
    resolution = models.TextField(
        "Kết quả xử lý", blank=True, help_text="Bắt buộc khi chuyển sang Đã giải quyết / Đã đóng."
    )
    satisfaction = models.PositiveSmallIntegerField(
        "Mức hài lòng của khách", choices=Satisfaction.choices, null=True, blank=True,
        help_text="Chỉ nhập sau khi phiếu đã được giải quyết.",
    )
    resolved_at = models.DateTimeField("Thời điểm giải quyết", null=True, blank=True, editable=False)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật lần cuối", auto_now=True)

    class Meta:
        verbose_name = "Phiếu hỗ trợ"
        verbose_name_plural = "Phiếu hỗ trợ"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} – {self.subject}" if self.code else self.subject

    @property
    def is_done(self):
        return self.status in self.DONE_STATUSES

    @property
    def is_overdue(self):
        """Quá hạn: chưa xong mà đã qua hạn, hoặc đã xong nhưng trễ hơn hạn."""
        if not self.due_at:
            return False
        return (self.resolved_at or timezone.now()) > self.due_at

    @property
    def resolution_hours(self):
        """Số giờ từ lúc tiếp nhận tới lúc giải quyết (None nếu chưa xong)."""
        if not (self.resolved_at and self.created_at):
            return None
        return round((self.resolved_at - self.created_at).total_seconds() / 3600, 1)

    @classmethod
    def open_overdue(cls):
        """Phiếu chưa xử lý xong và đã quá hạn – cần ưu tiên."""
        return cls.objects.exclude(status__in=cls.DONE_STATUSES).filter(due_at__lt=timezone.now())

    def clean(self):
        errors = {}
        if self.is_done and not (self.resolution or "").strip():
            errors["resolution"] = "Nhập kết quả xử lý trước khi chuyển sang Đã giải quyết / Đã đóng."
        if self.satisfaction and not self.is_done:
            errors["satisfaction"] = "Chỉ ghi mức hài lòng khi phiếu đã được giải quyết."
        if self.order_id and self.customer_id and self.order.customer_id != self.customer_id:
            errors["order"] = "Đơn hàng này không thuộc khách hàng đã chọn."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        now = timezone.now()
        with transaction.atomic():
            if not self.code:
                self.code = next_daily_code(SupportTicket, "HT")
            if not self.due_at:
                self.due_at = (self.created_at or now) + timedelta(hours=self.SLA_HOURS[self.priority])
            if self.is_done:
                self.resolved_at = self.resolved_at or now
            else:
                self.resolved_at = None  # phiếu được mở lại
            super().save(*args, **kwargs)


class TicketNote(Orderable):
    ticket = ParentalKey(SupportTicket, on_delete=models.CASCADE, related_name="notes")
    content = models.TextField("Nội dung")
    created_at = models.DateTimeField("Thời gian", auto_now_add=True)

    class Meta(Orderable.Meta):
        verbose_name = "Ghi chú xử lý"
        verbose_name_plural = "Ghi chú xử lý"

    def __str__(self):
        return self.content[:60]


# ====================================================================== Marketing
class Campaign(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        ZALO = "zalo", "Zalo"
        FACEBOOK = "facebook", "Facebook"
        PHONE = "phone", "Gọi điện"
        EVENT = "event", "Sự kiện"

    class Status(models.TextChoices):
        DRAFT = "draft", "Bản nháp"
        RUNNING = "running", "Đang chạy"
        FINISHED = "finished", "Đã kết thúc"
        CANCELLED = "cancelled", "Đã huỷ"

    name = models.CharField("Tên chiến dịch", max_length=200)
    channel = models.CharField("Kênh", max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    status = models.CharField("Trạng thái", max_length=20, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField("Ngày bắt đầu", default=timezone.localdate)
    end_date = models.DateField("Ngày kết thúc", null=True, blank=True)
    budget = models.DecimalField("Ngân sách (VNĐ)", max_digits=14, decimal_places=0, default=0)
    target_status = models.CharField(
        "Nhắm tới trạng thái khách", max_length=20, choices=Customer.Status.choices, blank=True,
        help_text="Bỏ trống = mọi trạng thái.",
    )
    target_source = models.CharField(
        "Nhắm tới nguồn khách", max_length=20, choices=Customer.Source.choices, blank=True,
        help_text="Bỏ trống = mọi nguồn.",
    )
    message = models.TextField("Thông điệp / nội dung gửi", blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người phụ trách",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaigns",
    )
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Chiến dịch marketing"
        verbose_name_plural = "Chiến dịch marketing"
        ordering = ["-start_date", "-created_at"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "Ngày kết thúc phải sau ngày bắt đầu."})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.status == self.Status.DRAFT:
                self.sync_members()

    # ------------------------------------------------------------ danh sách khách
    def matching_customers(self):
        customers = Customer.objects.all()
        if self.target_status:
            customers = customers.filter(status=self.target_status)
        if self.target_source:
            customers = customers.filter(source=self.target_source)
        return customers

    def sync_members(self):
        """Khi còn là Bản nháp: danh sách khách bám theo điều kiện nhắm tới.

        Chỉ đụng tới khách chưa liên hệ; khách đã có kết quả thì giữ nguyên.
        Từ lúc chiến dịch chạy, danh sách không tự đổi nữa (thêm/bớt tay ở "Khách trong chiến dịch").
        """
        matching = self.matching_customers()
        self.members.filter(response=CampaignMember.Response.PENDING).exclude(customer__in=matching).delete()
        existing = self.members.values_list("customer_id", flat=True)
        CampaignMember.objects.bulk_create(
            CampaignMember(campaign=self, customer=customer) for customer in matching.exclude(pk__in=existing)
        )

    # ------------------------------------------------------------ hiệu quả
    def count_members(self, *responses):
        members = self.members.all()
        return members.filter(response__in=responses).count() if responses else members.count()

    @property
    def member_count(self):
        return self.count_members()

    @property
    def contacted_count(self):
        return self.members.exclude(response=CampaignMember.Response.PENDING).count()

    @property
    def responded_count(self):
        return self.count_members(CampaignMember.Response.RESPONDED, CampaignMember.Response.CONVERTED)

    @property
    def converted_count(self):
        return self.count_members(CampaignMember.Response.CONVERTED)

    @staticmethod
    def percent(part, whole):
        return f"{part / whole:.0%}" if whole else "–"

    @property
    def response_rate(self):
        """Tỉ lệ phản hồi = khách phản hồi (kể cả đã mua) / khách đã liên hệ."""
        return self.percent(self.responded_count, self.contacted_count)

    @property
    def conversion_rate(self):
        """Tỉ lệ chuyển đổi = khách đã mua / khách đã liên hệ."""
        return self.percent(self.converted_count, self.contacted_count)

    @property
    def revenue(self):
        """Doanh thu ghi nhận: đơn Hoàn thành của khách đã chuyển đổi, đặt trong thời gian chiến dịch."""
        period = Q(order__created_at__date__gte=self.start_date)
        if self.end_date:
            period &= Q(order__created_at__date__lte=self.end_date)
        total = OrderItem.objects.filter(
            period,
            order__status=Order.Status.COMPLETED,
            order__customer__campaign_memberships__campaign=self,
            order__customer__campaign_memberships__response=CampaignMember.Response.CONVERTED,
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("unit_price"),
                    output_field=DecimalField(max_digits=18, decimal_places=0),
                )
            )
        )["total"]
        return total or Decimal("0")


class CampaignMember(models.Model):
    class Response(models.TextChoices):
        PENDING = "pending", "Chưa liên hệ"
        SENT = "sent", "Đã gửi"
        RESPONDED = "responded", "Đã phản hồi"
        CONVERTED = "converted", "Đã mua hàng"
        DECLINED = "declined", "Từ chối"

    campaign = models.ForeignKey(
        Campaign, verbose_name="Chiến dịch", on_delete=models.CASCADE, related_name="members"
    )
    customer = models.ForeignKey(
        Customer, verbose_name="Khách hàng", on_delete=models.CASCADE, related_name="campaign_memberships"
    )
    response = models.CharField(
        "Kết quả", max_length=20, choices=Response.choices, default=Response.PENDING
    )
    contacted_at = models.DateTimeField("Thời điểm liên hệ", null=True, blank=True)
    note = models.CharField("Ghi chú", max_length=255, blank=True)

    class Meta:
        verbose_name = "Khách trong chiến dịch"
        verbose_name_plural = "Khách trong chiến dịch"
        ordering = ["campaign", "customer__name"]
        constraints = [
            models.UniqueConstraint(fields=["campaign", "customer"], name="care_unique_campaign_customer"),
        ]

    def __str__(self):
        return f"{self.customer.name} – {self.campaign.name}"

    def save(self, *args, **kwargs):
        if self.response != self.Response.PENDING and not self.contacted_at:
            self.contacted_at = timezone.now()
        super().save(*args, **kwargs)
