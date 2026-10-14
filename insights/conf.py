"""Hằng số dùng chung của các module AI (docs/th2/HOP_DONG_DU_LIEU.md mục 6). Đổi phải báo cả nhóm."""

import os

from django.db.models import Max
from django.utils import timezone

CHURN_WINDOW_DAYS = 180   # không mua trong 180 ngày = rời bỏ
BACKTEST_MONTHS = 6       # số tháng cuối giữ lại để kiểm tra mô hình dự báo
FORECAST_HORIZON = 6      # số tháng dự báo tới
RISK_HIGH = 0.6           # xác suất rời bỏ ≥ 0,6 → rủi ro Cao
RISK_MEDIUM = 0.3         # ≥ 0,3 → Trung bình, còn lại Thấp
RANDOM_STATE = 42
# Số câu dùng để chấm và so sánh các phương pháp cảm xúc (0 = tất cả). Mọi phương pháp chấm cùng tập mẫu này.
SENTIMENT_SAMPLE = int(os.getenv("SENTIMENT_SAMPLE", "600"))


def reference_date():
    """Ngày tham chiếu = ngày (giờ Việt Nam) của đơn hàng muộn nhất trong CSDL; không có đơn thì là hôm nay."""
    from crm.models import Order

    latest = Order.objects.aggregate(latest=Max("created_at"))["latest"]
    return timezone.localtime(latest).date() if latest else timezone.localdate()


def risk_band(probability):
    if probability >= RISK_HIGH:
        return "high"
    if probability >= RISK_MEDIUM:
        return "medium"
    return "low"
