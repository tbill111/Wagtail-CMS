import json
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import AIReport, Customer, InteractionLog, OrderItem
from .services import AIServiceError, get_ai_service
from .services.ai_service import ALLOWED_TONES, DEFAULT_TONE

MAX_MESSAGE_LENGTH = 2000

staff_required = staff_member_required(login_url=settings.LOGIN_URL)


def api_staff_required(view_func):
    """Như ``staff_required`` nhưng trả JSON thay vì chuyển hướng (dùng cho API AJAX)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return json_error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.", 401)
        if not (user.is_active and user.is_staff):
            return json_error("Bạn không có quyền sử dụng chức năng này.", 403)
        return view_func(request, *args, **kwargs)

    return wrapper


def json_error(message, status):
    return JsonResponse({"ok": False, "error": message}, status=status)


def parse_json_body(request):
    """Đọc body JSON (hoặc form-urlencoded). Trả về dict hoặc None nếu sai định dạng."""
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None
    return request.POST.dict()


def clean_text(value, *, field_label, required=True, max_length=MAX_MESSAGE_LENGTH):
    """Chuẩn hoá chuỗi đầu vào; trả về (giá_trị, thông_báo_lỗi)."""
    if value is None:
        value = ""
    if not isinstance(value, str):
        return None, f"{field_label} không hợp lệ."
    value = value.strip()
    if required and not value:
        return None, f"Vui lòng nhập {field_label.lower()}."
    if len(value) > max_length:
        return None, f"{field_label} tối đa {max_length} ký tự."
    return value, None


# ---------------------------------------------------------------- trang HTML
@require_GET
@staff_required
def dashboard(request):
    now = timezone.localtime()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue = OrderItem.objects.filter(order__status="completed").aggregate(
        total=Sum(
            ExpressionWrapper(
                F("quantity") * F("unit_price"),
                output_field=DecimalField(max_digits=18, decimal_places=0),
            )
        )
    )["total"]
    high_priority_customers = Customer.objects.filter(ai_priority="high").order_by("-ai_analyzed_at")[:5]
    context = {
        "high_priority_customers": high_priority_customers,
        "stats": {
            "total_customers": Customer.objects.count(),
            "new_customers": Customer.objects.filter(created_at__gte=month_start).count(),
            "revenue": revenue or 0,
            "recent_interactions": InteractionLog.objects.filter(
                created_at__gte=now - timedelta(days=7)
            ).count(),
        },
        "latest_interactions": InteractionLog.objects.select_related("customer", "staff")[:5],
    }
    return render(request, "crm/dashboard.html", context)


@require_GET
@staff_required
def customer_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    customers = Customer.objects.select_related("assigned_staff").order_by("-created_at")
    if query:
        customers = customers.filter(
            Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query)
        )
    if status in Customer.Status.values:
        customers = customers.filter(status=status)
    else:
        status = ""

    priority = request.GET.get("priority", "").strip()
    if priority in Customer.Priority.values:
        customers = customers.filter(ai_priority=priority)
    else:
        priority = ""

    page_obj = Paginator(customers, 10).get_page(request.GET.get("page"))
    context = {
        "page_obj": page_obj,
        "customers": page_obj.object_list,
        "query": query,
        "status": status,
        "status_choices": Customer.Status.choices,
        "priority": priority,
        "priority_choices": Customer.Priority.choices,
    }
    return render(request, "crm/customer_list.html", context)


@require_GET
@staff_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("assigned_staff"), pk=pk)
    context = {
        "customer": customer,
        "orders": customer.orders.prefetch_related("items").order_by("-created_at"),
        "interactions": customer.interactions.select_related("staff"),
        "tones": ALLOWED_TONES,
        "default_tone": DEFAULT_TONE,
        "channels": InteractionLog.Channel.choices,
        "ai_is_mock": get_ai_service().is_mock,
        "max_message_length": MAX_MESSAGE_LENGTH,
    }
    return render(request, "crm/customer_detail.html", context)


# ------------------------------------------------------------------- API AI
@require_POST
@api_staff_required
def api_suggest_reply(request, pk):
    data = parse_json_body(request)
    if data is None:
        return json_error("Dữ liệu gửi lên không đúng định dạng JSON.", 400)

    message, error = clean_text(data.get("message"), field_label="Tin nhắn của khách")
    if error:
        return json_error(error, 400)
    tone = data.get("tone") or DEFAULT_TONE
    if tone not in ALLOWED_TONES:
        return json_error("Giọng văn không hợp lệ.", 400)

    customer = Customer.objects.filter(pk=pk).first()
    if customer is None:
        return json_error("Không tìm thấy khách hàng.", 404)

    service = get_ai_service()
    try:
        reply = service.suggest_reply(customer, message, tone=tone)
    except AIServiceError as exc:
        return json_error(str(exc), 503)
    return JsonResponse(
        {"ok": True, "reply": reply, "mock": service.is_mock, "provider": service.last_provider_label}
    )


@require_POST
@api_staff_required
def api_save_interaction(request, pk):
    data = parse_json_body(request)
    if data is None:
        return json_error("Dữ liệu gửi lên không đúng định dạng JSON.", 400)

    message, error = clean_text(data.get("message"), field_label="Tin nhắn của khách")
    if error:
        return json_error(error, 400)
    final_reply, error = clean_text(
        data.get("final_reply"), field_label="Nội dung phản hồi", max_length=5000
    )
    if error:
        return json_error(error, 400)
    ai_reply, error = clean_text(
        data.get("ai_suggested_reply"), field_label="Gợi ý AI", required=False, max_length=5000
    )
    if error:
        return json_error(error, 400)
    channel = data.get("channel") or InteractionLog.Channel.EMAIL
    if channel not in InteractionLog.Channel.values:
        return json_error("Kênh liên hệ không hợp lệ.", 400)

    customer = Customer.objects.filter(pk=pk).first()
    if customer is None:
        return json_error("Không tìm thấy khách hàng.", 404)

    interaction = InteractionLog.objects.create(
        customer=customer,
        channel=channel,
        customer_message=message,
        ai_suggested_reply=ai_reply,
        final_reply=final_reply,
        is_ai_generated=bool(ai_reply),
        staff=request.user,
    )
    html = render_to_string(
        "crm/_interaction_item.html", {"interaction": interaction, "is_new": True}, request=request
    )
    return JsonResponse({"ok": True, "id": interaction.pk, "interaction_html": html}, status=201)


@require_POST
@api_staff_required
def api_analyze_customer(request, pk):
    customer = Customer.objects.filter(pk=pk).first()
    if customer is None:
        return json_error("Không tìm thấy khách hàng.", 404)
    service = get_ai_service()
    try:
        result = service.analyze_customer(customer)
    except AIServiceError as exc:
        return json_error(str(exc), 503)
    customer.refresh_from_db()  # reload ai_analyzed_at
    from .templatetags.crm_tags import STATUS_BADGES
    return JsonResponse({
        "ok": True,
        "data": {
            "sentiment": result["sentiment"],
            "sentiment_display": customer.get_ai_sentiment_display(),
            "priority": result["priority"],
            "priority_display": customer.get_ai_priority_display(),
            "suggested_status": result["suggested_status"],
            "suggested_status_display": customer.get_ai_suggested_status_display(),
            "summary": result["summary"],
            "next_actions": result["next_actions"],
            "analyzed_at": customer.ai_analyzed_at.strftime("%d/%m/%Y %H:%M") if customer.ai_analyzed_at else "",
        },
        "mock": service.is_mock,
        "provider": service.last_provider_label,
    })


@require_POST
@api_staff_required
def api_apply_status(request, pk):
    customer = Customer.objects.filter(pk=pk).first()
    if customer is None:
        return json_error("Không tìm thấy khách hàng.", 404)
    if not customer.ai_suggested_status:
        return json_error("Chưa có đề xuất trạng thái từ AI.", 400)
    if customer.ai_suggested_status == customer.status:
        return json_error("Trạng thái đề xuất trùng với trạng thái hiện tại.", 400)
    from .templatetags.crm_tags import STATUS_BADGES
    customer.status = customer.ai_suggested_status
    customer.save(update_fields=["status"])
    return JsonResponse({
        "ok": True,
        "status": customer.status,
        "status_display": customer.get_status_display(),
        "badge_class": STATUS_BADGES.get(customer.status, "text-bg-secondary"),
    })


@require_GET
@staff_required
def report_page(request):
    from .services.ai_service import GeminiCRMService
    stats = GeminiCRMService.build_report_stats()
    recent_reports = AIReport.objects.select_related("created_by").order_by("-created_at")[:5]
    context = {
        "stats": stats,
        "recent_reports": recent_reports,
        "ai_is_mock": get_ai_service().is_mock,
    }
    return render(request, "crm/report.html", context)


@require_POST
@api_staff_required
def api_generate_report(request):
    from .models import Customer
    if Customer.objects.count() == 0:
        return json_error("Chưa có dữ liệu khách hàng để tạo báo cáo.", 400)
    service = get_ai_service()
    try:
        result = service.generate_report()
    except AIServiceError as exc:
        return json_error(str(exc), 503)
    # Lưu lịch sử
    AIReport.objects.create(
        content=result["insight"],
        stats=result["stats"],
        provider=service.last_provider_label,
        is_mock=service.is_mock,
        created_by=request.user if request.user.is_authenticated else None,
    )
    return JsonResponse({
        "ok": True,
        "stats": result["stats"],
        "insight": result["insight"],
        "generated_at": result["generated_at"],
        "mock": service.is_mock,
        "provider": service.last_provider_label,
    })
