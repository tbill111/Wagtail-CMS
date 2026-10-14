"""Truy vấn số liệu cho biểu đồ Tổng quan và báo cáo AI. Mọi giá trị trả về đều JSON được."""

from datetime import date

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Customer, InteractionLog, Order, OrderItem, Product

MONEY = DecimalField(max_digits=18, decimal_places=0)
LINE_TOTAL = ExpressionWrapper(F("quantity") * F("unit_price"), output_field=MONEY)
COMPLETED_ITEMS = Q(order__status=Order.Status.COMPLETED)


def data_as_of():
    """Mốc tính "tháng này", "7 ngày qua", "12 tháng gần nhất".

    Bình thường là hiện tại. Nếu dữ liệu mới nhất (đơn hàng, tương tác) đã cũ hơn đầu tháng này – ví dụ CSDL chứa bộ dữ
    liệu lịch sử – thì lấy thời điểm dữ liệu mới nhất, để các ô số liệu không toàn 0 và biểu đồ không trống.
    """
    now = timezone.localtime()
    latest = [
        Order.objects.aggregate(m=Max("created_at"))["m"],
        InteractionLog.objects.aggregate(m=Max("created_at"))["m"],
    ]
    latest = max((value for value in latest if value), default=None)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return timezone.localtime(latest) if latest and latest < month_start else now


def monthly_revenue(months=12, as_of=None):
    """Doanh thu đơn Hoàn thành theo tháng, đủ ``months`` tháng tính đến ``as_of`` (tháng không có đơn = 0)."""
    today = (as_of or timezone.localtime()).date()
    keys = []
    year, month = today.year, today.month
    for _ in range(months):
        keys.append(date(year, month, 1))
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    keys.reverse()

    rows = (
        OrderItem.objects.filter(COMPLETED_ITEMS, order__created_at__date__gte=keys[0])
        .annotate(month=TruncMonth("order__created_at", tzinfo=timezone.get_current_timezone()))
        .values("month")
        .annotate(total=Sum(LINE_TOTAL))
    )
    totals = {row["month"].date() if hasattr(row["month"], "date") else row["month"]: row["total"] for row in rows}
    return [{"label": f"T{key.month}/{key.year}", "value": int(totals.get(key) or 0)} for key in keys]


def customers_by_status():
    counts = dict(Customer.objects.order_by().values_list("status").annotate(n=Count("pk")))
    return [{"label": label, "value": counts.get(value, 0)} for value, label in Customer.Status.choices]


def top_customers(limit=5):
    rows = (
        Customer.objects.annotate(
            spent=Sum(
                F("orders__items__quantity") * F("orders__items__unit_price"),
                filter=Q(orders__status=Order.Status.COMPLETED),
                output_field=MONEY,
            )
        )
        .filter(spent__gt=0)
        .order_by("-spent", "name")
        .values("name", "spent")[:limit]
    )
    return [{"label": row["name"], "value": int(row["spent"])} for row in rows]


def top_products(limit=5):
    """Sản phẩm bán chạy theo số lượng đã bán (đơn Hoàn thành)."""
    rows = (
        OrderItem.objects.filter(COMPLETED_ITEMS, product__isnull=False)
        .values("product__sku", "product__name", "product__unit")
        .annotate(sold=Sum("quantity"), revenue=Sum(LINE_TOTAL))
        .order_by("-sold", "-revenue", "product__name")[:limit]
    )
    return [
        {
            "label": row["product__name"],
            "sku": row["product__sku"],
            "unit": row["product__unit"],
            "value": row["sold"],
            "revenue": int(row["revenue"] or 0),
        }
        for row in rows
    ]


def low_stock_products():
    return [
        {"sku": p.sku, "name": p.name, "unit": p.unit, "stock": p.stock, "min_stock": p.min_stock}
        for p in Product.low_stock().order_by("stock", "name")
    ]
