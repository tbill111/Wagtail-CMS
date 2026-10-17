"""Đọc kết quả AI để hiển thị trong SmartCRM – nhẹ, không import thư viện học máy."""

from django.db.models import Case, IntegerField, Value, When

from .models import ChurnScore, ModelRun

# Trùng tên trong ai.method_label (sql/superset/03_ai_views.sql) để trang khách và dashboard gọi giống nhau
CHURN_METHOD_LABELS = {
    "rfm_rule": "Luật RFM",
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
}
RISK_DISPLAY = {
    "high": ("Cao", "text-bg-danger"),
    "medium": ("Trung bình", "text-bg-warning"),
    "low": ("Thấp", "text-bg-success"),
}


def latest_customer_risk(customer):
    """Điểm rủi ro rời bỏ của khách theo phương pháp được chọn trong batch churn mới nhất, hoặc None.

    Ưu tiên batch thật hơn batch "demo" (seed_ai_demo). Một truy vấn. Gắn thêm thuộc tính để hiển thị:
    ``percent``, ``risk_label``, ``badge_class``, ``method_label``.
    """
    is_demo = Case(When(run__batch="demo", then=Value(1)), default=Value(0), output_field=IntegerField())
    score = (
        ChurnScore.objects.filter(customer=customer, run__module=ModelRun.Module.CHURN,
                                  run__status=ModelRun.Status.SUCCESS, run__is_selected=True)
        .select_related("run").annotate(is_demo=is_demo).order_by("is_demo", "-run__started_at").first()
    )
    if score:
        score.percent = round(score.probability * 100)
        score.risk_label, score.badge_class = RISK_DISPLAY.get(score.risk_band, ("Không xác định",
                                                                                 "text-bg-secondary"))
        score.method_label = CHURN_METHOD_LABELS.get(score.run.method, score.run.method)
    return score
