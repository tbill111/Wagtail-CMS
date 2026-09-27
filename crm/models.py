from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.models import Orderable


class Customer(models.Model):
    class Status(models.TextChoices):
        LEAD = "lead", "Tiềm năng"
        CARING = "caring", "Đang chăm sóc"
        CUSTOMER = "customer", "Đã mua hàng"
        CHURNED = "churned", "Đã rời bỏ"

    class Source(models.TextChoices):
        WEBSITE = "website", "Website"
        FACEBOOK = "facebook", "Facebook"
        REFERRAL = "referral", "Giới thiệu"
        OTHER = "other", "Khác"

    name = models.CharField("Họ và tên", max_length=150)
    email = models.EmailField("Email", unique=True)
    phone = models.CharField("Số điện thoại", max_length=20, blank=True)
    company = models.CharField("Công ty", max_length=150, blank=True)
    status = models.CharField(
        "Trạng thái", max_length=20, choices=Status.choices, default=Status.LEAD
    )
    source = models.CharField(
        "Nguồn khách", max_length=20, choices=Source.choices, default=Source.WEBSITE
    )
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Nhân viên phụ trách",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_customers",
    )

    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Tích cực"
        NEUTRAL = "neutral", "Trung lập"
        NEGATIVE = "negative", "Tiêu cực"

    class Priority(models.TextChoices):
        HIGH = "high", "Cao"
        MEDIUM = "medium", "Trung bình"
        LOW = "low", "Thấp"

    ai_sentiment = models.CharField(
        "Cảm xúc AI", max_length=20, choices=Sentiment.choices, blank=True
    )
    ai_priority = models.CharField(
        "Ưu tiên AI", max_length=20, choices=Priority.choices, blank=True
    )
    ai_suggested_status = models.CharField(
        "Trạng thái đề xuất AI", max_length=20, choices=Status.choices, blank=True
    )
    ai_summary = models.TextField("Tóm tắt AI", blank=True)
    ai_next_actions = models.JSONField("Hành động tiếp theo (AI)", default=list, blank=True)
    ai_analyzed_at = models.DateTimeField("Thời điểm phân tích AI", null=True, blank=True)

    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật lần cuối", auto_now=True)

    class Meta:
        verbose_name = "Khách hàng"
        verbose_name_plural = "Khách hàng"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.email})"

    @property
    def total_spent(self):
        """Tổng giá trị các đơn hàng ở trạng thái Hoàn thành."""
        result = OrderItem.objects.filter(
            order__customer=self, order__status=Order.Status.COMPLETED
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("unit_price"),
                    output_field=DecimalField(max_digits=18, decimal_places=0),
                )
            )
        )["total"]
        return result or Decimal("0")


class Order(ClusterableModel):
    class Status(models.TextChoices):
        NEW = "new", "Mới"
        PROCESSING = "processing", "Đang xử lý"
        COMPLETED = "completed", "Hoàn thành"
        CANCELLED = "cancelled", "Huỷ"

    code = models.CharField("Mã đơn", max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        Customer,
        verbose_name="Khách hàng",
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        "Trạng thái", max_length=20, choices=Status.choices, default=Status.NEW
    )
    note = models.TextField("Ghi chú", blank=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Đơn hàng"
        verbose_name_plural = "Đơn hàng"
        ordering = ["-created_at"]

    def __str__(self):
        return self.code or "Đơn hàng mới"

    @staticmethod
    def generate_code(date=None):
        """Sinh mã dạng DH-YYYYMMDD-0001, tăng dần theo ngày."""
        date = date or timezone.localdate()
        prefix = f"DH-{date:%Y%m%d}-"
        last_code = (
            Order.objects.filter(code__startswith=prefix)
            .order_by("-code")
            .values_list("code", flat=True)
            .first()
        )
        next_number = int(last_code.rsplit("-", 1)[1]) + 1 if last_code else 1
        return f"{prefix}{next_number:04d}"

    def save(self, *args, **kwargs):
        if not self.code:
            with transaction.atomic():
                self.code = self.generate_code()
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @property
    def total_amount(self):
        return sum((item.subtotal for item in self.items.all()), Decimal("0"))


class OrderItem(Orderable):
    order = ParentalKey(Order, on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField("Sản phẩm / dịch vụ", max_length=200)
    quantity = models.PositiveIntegerField("Số lượng", default=1)
    unit_price = models.DecimalField("Đơn giá (VNĐ)", max_digits=14, decimal_places=0)

    class Meta(Orderable.Meta):
        verbose_name = "Dòng sản phẩm"
        verbose_name_plural = "Dòng sản phẩm"

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    @property
    def subtotal(self):
        return (self.unit_price or Decimal("0")) * (self.quantity or 0)


class InteractionLog(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        PHONE = "phone", "Điện thoại"
        CHAT = "chat", "Chat"
        IN_PERSON = "in_person", "Trực tiếp"

    customer = models.ForeignKey(
        Customer,
        verbose_name="Khách hàng",
        on_delete=models.CASCADE,
        related_name="interactions",
    )
    channel = models.CharField(
        "Kênh", max_length=20, choices=Channel.choices, default=Channel.EMAIL
    )
    customer_message = models.TextField("Tin nhắn của khách")
    ai_suggested_reply = models.TextField("Gợi ý phản hồi của AI", blank=True)
    final_reply = models.TextField("Phản hồi đã gửi", blank=True)
    is_ai_generated = models.BooleanField("Có dùng AI", default=False)
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Nhân viên xử lý",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="interactions",
    )
    created_at = models.DateTimeField("Thời gian", auto_now_add=True)

    class Meta:
        verbose_name = "Lịch sử tương tác"
        verbose_name_plural = "Lịch sử tương tác"
        ordering = ["-created_at"]

    def __str__(self):
        when = timezone.localtime(self.created_at).strftime("%d/%m/%Y %H:%M") if self.created_at else ""
        return f"{self.customer.name} – {self.get_channel_display()} {when}".strip()


class AIReport(models.Model):
    """Lưu lịch sử báo cáo nhận định nhanh do AI tạo."""

    content = models.TextField("Nội dung nhận định")
    stats = models.JSONField("Số liệu tổng hợp", default=dict)
    provider = models.CharField("Nhà cung cấp AI", max_length=100, blank=True)
    is_mock = models.BooleanField("Chế độ mô phỏng", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người tạo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_reports",
    )
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Báo cáo AI"
        verbose_name_plural = "Báo cáo AI"
        ordering = ["-created_at"]

    def __str__(self):
        when = timezone.localtime(self.created_at).strftime("%d/%m/%Y %H:%M") if self.created_at else ""
        return f"Báo cáo AI – {when}"
