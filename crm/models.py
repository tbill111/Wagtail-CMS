from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.signals import pre_delete
from django.dispatch import receiver
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

    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Tích cực"
        NEUTRAL = "neutral", "Trung lập"
        NEGATIVE = "negative", "Tiêu cực"

    class Priority(models.TextChoices):
        HIGH = "high", "Cao"
        MEDIUM = "medium", "Trung bình"
        LOW = "low", "Thấp"

    name =models.CharField("Họ và tên", max_length=150)
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

    # Kết quả phân loại khách hàng bằng AI (do GeminiCRMService.analyze_customer ghi)
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
    ai_provider = models.CharField("AI đã phân tích", max_length=100, blank=True)

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


class Product(models.Model):
    sku = models.CharField("Mã SKU", max_length=30, unique=True)
    name = models.CharField("Tên sản phẩm / dịch vụ", max_length=200)
    unit = models.CharField("Đơn vị tính", max_length=30, default="cái")
    price = models.DecimalField("Giá bán (VNĐ)", max_digits=14, decimal_places=0)
    track_stock = models.BooleanField(
        "Quản lý tồn kho", default=True,
        help_text="Bỏ chọn với dịch vụ / gói phần mềm (không có hàng trong kho).",
    )
    stock = models.PositiveIntegerField("Tồn kho", default=0)
    min_stock = models.PositiveIntegerField(
        "Tồn kho tối thiểu", default=0, help_text="Cảnh báo sắp hết hàng khi tồn kho ≤ mức này."
    )
    is_active = models.BooleanField("Đang kinh doanh", default=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Sản phẩm"
        verbose_name_plural = "Sản phẩm"
        ordering = ["name"]

    def __str__(self):
        return f"{self.sku} – {self.name}"

    @property
    def is_low_stock(self):
        return self.track_stock and self.stock <= self.min_stock

    @classmethod
    def low_stock(cls):
        return cls.objects.filter(is_active=True, track_stock=True, stock__lte=F("min_stock"))


class InsufficientStockError(ValidationError):
    """Hoàn thành đơn hàng nhưng kho không đủ hàng để xuất."""


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
    # {product_id: số lượng đã trừ kho} – để hoàn/trừ đúng phần chênh lệch mỗi lần lưu
    stock_snapshot = models.JSONField("Số lượng đã trừ kho", default=dict, blank=True, editable=False)
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
        with transaction.atomic():
            if not self.code:
                self.code = self.generate_code()
            # ClusterableModel.save() ghi luôn các dòng sản phẩm, nên sau đó mới đồng bộ kho
            super().save(*args, **kwargs)
            self.sync_stock()

    # ------------------------------------------------------------ tồn kho
    def desired_stock(self, items):
        """Số lượng cần trừ kho theo từng sản phẩm; ``items`` là các cặp (product, quantity)."""
        desired = defaultdict(int)
        if self.status == self.Status.COMPLETED:
            for product, quantity in items:
                if product is not None and product.track_stock and quantity:
                    desired[product.pk] += quantity
        return dict(desired)

    def stock_delta(self, desired):
        """Chênh lệch cần trừ thêm (dương) hoặc hoàn lại (âm) so với lần lưu trước."""
        previous = {int(pk): qty for pk, qty in (self.stock_snapshot or {}).items()}
        delta = {pk: desired.get(pk, 0) - previous.get(pk, 0) for pk in desired.keys() | previous.keys()}
        return {pk: qty for pk, qty in delta.items() if qty}

    @staticmethod
    def stock_shortages(delta):
        """Thông báo cho các sản phẩm không đủ tồn kho để trừ ``delta``."""
        need = {pk: qty for pk, qty in delta.items() if qty > 0}
        return [
            f"{product.name} ({product.sku}): cần xuất {need[pk]}, tồn kho chỉ còn {product.stock}"
            for pk, product in Product.objects.in_bulk(need).items()
            if product.stock < need[pk]
        ]

    def sync_stock(self):
        """Trừ kho khi đơn Hoàn thành; hoàn kho khi đơn rời trạng thái Hoàn thành hoặc bị sửa."""
        items = OrderItem.objects.filter(order_id=self.pk).select_related("product")
        desired = self.desired_stock((item.product, item.quantity) for item in items)
        delta = self.stock_delta(desired)
        if not delta:
            return
        shortages = self.stock_shortages(delta)
        if shortages:
            raise InsufficientStockError("Không đủ hàng trong kho: " + "; ".join(shortages))
        for pk, qty in delta.items():
            Product.objects.filter(pk=pk).update(stock=F("stock") - qty)
        self.stock_snapshot = {str(pk): qty for pk, qty in desired.items()}
        Order.objects.filter(pk=self.pk).update(stock_snapshot=self.stock_snapshot)

    @property
    def total_amount(self):
        return sum((item.subtotal for item in self.items.all()), Decimal("0"))


class OrderItem(Orderable):
    order = ParentalKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        verbose_name="Sản phẩm",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    product_name = models.CharField(
        "Tên hiển thị", max_length=200, blank=True,
        help_text="Bỏ trống để lấy tên sản phẩm đã chọn.",
    )
    quantity = models.PositiveIntegerField("Số lượng", default=1)
    unit_price = models.DecimalField(
        "Đơn giá (VNĐ)", max_digits=14, decimal_places=0, blank=True,
        help_text="Bỏ trống để lấy giá bán của sản phẩm.",
    )

    class Meta(Orderable.Meta):
        verbose_name = "Dòng sản phẩm"
        verbose_name_plural = "Dòng sản phẩm"

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    def fill_from_product(self):
        if self.product_id:
            if not self.product_name:
                self.product_name = self.product.name
            if self.unit_price is None:
                self.unit_price = self.product.price

    def clean(self):
        self.fill_from_product()
        if not self.product_name:
            raise ValidationError({"product": "Chọn sản phẩm hoặc nhập tên hiển thị."})
        if self.unit_price is None:
            raise ValidationError({"unit_price": "Vui lòng nhập đơn giá."})

    def save(self, *args, **kwargs):
        self.fill_from_product()
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return (self.unit_price or Decimal("0")) * (self.quantity or 0)


@receiver(pre_delete, sender=Order)
def restore_stock_on_order_delete(sender, instance, **kwargs):
    """Xoá đơn đã trừ kho (kể cả xoá theo khách hàng) thì trả hàng về kho."""
    for pk, qty in (instance.stock_snapshot or {}).items():
        Product.objects.filter(pk=int(pk)).update(stock=F("stock") + qty)


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
