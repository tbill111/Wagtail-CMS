"""Bảng kết quả của các mô hình AI (TH2). Cấu trúc theo docs/th2/HOP_DONG_DU_LIEU.md mục 4 – đổi phải báo cả nhóm."""

from django.db import models

from crm.models import Customer, InteractionLog

SENTIMENT_CHOICES = [("positive", "Tích cực"), ("neutral", "Trung lập"), ("negative", "Tiêu cực")]
MONEY = {"max_digits": 18, "decimal_places": 0, "null": True, "blank": True}


class ModelRun(models.Model):
    """Một lần chạy một phương pháp của một module. Cùng ``batch`` = cùng một lần chạy run_ai_pipeline."""

    class Module(models.TextChoices):
        FORECAST = "forecast", "Dự báo doanh thu"
        CHURN = "churn", "Dự đoán khách rời bỏ"
        SENTIMENT = "sentiment", "Phân tích cảm xúc"

    class Status(models.TextChoices):
        SUCCESS = "success", "Thành công"
        FAILED = "failed", "Lỗi"

    batch = models.CharField("Lần chạy", max_length=20, db_index=True)
    module = models.CharField("Module", max_length=20, choices=Module.choices)
    method = models.CharField("Phương pháp", max_length=40)
    is_selected = models.BooleanField("Được chọn", default=False)
    status = models.CharField("Trạng thái", max_length=20, choices=Status.choices, default=Status.SUCCESS)
    started_at = models.DateTimeField("Bắt đầu")
    finished_at = models.DateTimeField("Kết thúc", null=True, blank=True)
    n_rows = models.PositiveIntegerField("Số dòng kết quả", default=0)
    metrics = models.JSONField("Chỉ số đánh giá", default=dict, blank=True)
    params = models.JSONField("Tham số", default=dict, blank=True)
    notes = models.TextField("Ghi chú", blank=True)

    class Meta:
        verbose_name = "Lần chạy mô hình"
        verbose_name_plural = "Lần chạy mô hình"
        ordering = ["-started_at", "module", "method"]

    def __str__(self):
        return f"{self.batch} · {self.get_module_display()} · {self.method}"


class RevenueForecast(models.Model):
    class Kind(models.TextChoices):
        HISTORY = "history", "Lịch sử"
        BACKTEST = "backtest", "Kiểm tra lại"
        FUTURE = "future", "Dự báo"

    run = models.ForeignKey(ModelRun, verbose_name="Lần chạy", on_delete=models.CASCADE, related_name="forecasts")
    month = models.DateField("Tháng")
    kind = models.CharField("Loại", max_length=10, choices=Kind.choices)
    actual = models.DecimalField("Doanh thu thực tế (VNĐ)", **MONEY)
    forecast = models.DecimalField("Dự báo (VNĐ)", **MONEY)
    lower = models.DecimalField("Cận dưới 95% (VNĐ)", **MONEY)
    upper = models.DecimalField("Cận trên 95% (VNĐ)", **MONEY)

    class Meta:
        verbose_name = "Dự báo doanh thu"
        verbose_name_plural = "Dự báo doanh thu"
        ordering = ["run", "month"]
        constraints = [models.UniqueConstraint(fields=["run", "month", "kind"], name="uniq_forecast_run_month_kind")]


class ChurnScore(models.Model):
    class RiskBand(models.TextChoices):
        HIGH = "high", "Cao"
        MEDIUM = "medium", "Trung bình"
        LOW = "low", "Thấp"

    run = models.ForeignKey(ModelRun, verbose_name="Lần chạy", on_delete=models.CASCADE, related_name="churn_scores")
    customer = models.ForeignKey(Customer, verbose_name="Khách hàng", on_delete=models.CASCADE,
                                 related_name="churn_scores")
    probability = models.FloatField("Xác suất rời bỏ")
    risk_band = models.CharField("Mức rủi ro", max_length=10, choices=RiskBand.choices)

    class Meta:
        verbose_name = "Điểm rủi ro rời bỏ"
        verbose_name_plural = "Điểm rủi ro rời bỏ"
        constraints = [models.UniqueConstraint(fields=["run", "customer"], name="uniq_churn_run_customer")]


class SentimentLabel(models.Model):
    """Nhãn cảm xúc đúng (từ bộ dữ liệu) của một tin nhắn – dùng để chấm điểm các mô hình cảm xúc."""

    interaction = models.OneToOneField(InteractionLog, verbose_name="Tương tác", on_delete=models.CASCADE,
                                       related_name="sentiment_label")
    label = models.CharField("Nhãn đúng", max_length=10, choices=SENTIMENT_CHOICES)
    source = models.CharField("Nguồn nhãn", max_length=200)

    class Meta:
        verbose_name = "Nhãn cảm xúc"
        verbose_name_plural = "Nhãn cảm xúc"


class SentimentResult(models.Model):
    run = models.ForeignKey(ModelRun, verbose_name="Lần chạy", on_delete=models.CASCADE, related_name="sentiments")
    interaction = models.ForeignKey(InteractionLog, verbose_name="Tương tác", on_delete=models.CASCADE,
                                    related_name="sentiment_results")
    label = models.CharField("Nhãn dự đoán", max_length=10, choices=SENTIMENT_CHOICES)
    confidence = models.FloatField("Độ tin cậy", null=True, blank=True)
    latency_ms = models.PositiveIntegerField("Thời gian (ms)", null=True, blank=True)

    class Meta:
        verbose_name = "Kết quả cảm xúc"
        verbose_name_plural = "Kết quả cảm xúc"
        constraints = [models.UniqueConstraint(fields=["run", "interaction"], name="uniq_sentiment_run_interaction")]
