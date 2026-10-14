"""Truy vấn dữ liệu dùng chung cho các module AI."""

import calendar
from datetime import date

import pandas as pd
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from crm.analytics import COMPLETED_ITEMS, LINE_TOTAL
from crm.models import OrderItem

from .conf import reference_date


def last_full_month(as_of=None):
    """Ngày 1 của tháng trọn vẹn cuối cùng tính đến ``as_of`` (mặc định reference_date)."""
    as_of = as_of or reference_date()
    if as_of.day == calendar.monthrange(as_of.year, as_of.month)[1]:
        return date(as_of.year, as_of.month, 1)
    year, month = (as_of.year, as_of.month - 1) if as_of.month > 1 else (as_of.year - 1, 12)
    return date(year, month, 1)


def monthly_revenue_series(as_of=None):
    """Doanh thu đơn Hoàn thành theo tháng (giờ Việt Nam), từ tháng đầu có doanh thu đến tháng trọn vẹn cuối cùng.

    Trả về pandas Series kiểu int (VNĐ), chỉ mục là ngày đầu tháng, tần suất "MS"; tháng không có đơn = 0.
    Cùng quy ước doanh thu với trang Tổng quan /crm/ và view analytics của TH1.
    """
    end = last_full_month(as_of)
    rows = (
        OrderItem.objects.filter(COMPLETED_ITEMS)
        .annotate(month=TruncMonth("order__created_at", tzinfo=timezone.get_current_timezone()))
        .values("month")
        .annotate(total=Sum(LINE_TOTAL))
        .order_by("month")
    )
    totals = {}
    for row in rows:
        month = row["month"].date() if hasattr(row["month"], "date") else row["month"]
        if month <= end:
            totals[month] = int(row["total"] or 0)
    if not totals:
        return pd.Series(dtype="int64")
    index = pd.date_range(min(totals), end, freq="MS")
    return pd.Series([totals.get(day.date(), 0) for day in index], index=index, dtype="int64", name="revenue")
