from django import template

from ..services.ai_service import format_vnd

register = template.Library()

STATUS_BADGES = {
    "lead": "text-bg-secondary",
    "caring": "text-bg-warning",
    "customer": "text-bg-success",
    "churned": "text-bg-danger",
}

ORDER_BADGES = {
    "new": "text-bg-info",
    "processing": "text-bg-warning",
    "completed": "text-bg-success",
    "cancelled": "text-bg-danger",
}


@register.filter
def vnd(amount):
    """Định dạng tiền Việt: 1500000 -> 1.500.000 ₫"""
    return format_vnd(amount)


@register.filter
def status_badge(status):
    return STATUS_BADGES.get(status, "text-bg-secondary")


@register.filter
def order_badge(status):
    return ORDER_BADGES.get(status, "text-bg-secondary")


@register.simple_tag(takes_context=True)
def query_string(context, **kwargs):
    """Giữ lại tham số lọc hiện tại khi chuyển trang."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else ""
