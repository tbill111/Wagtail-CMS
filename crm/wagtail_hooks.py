from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import AIReport, Customer, InteractionLog, Order


class CustomerViewSet(SnippetViewSet):
    model = Customer
    icon = "user"
    menu_label = "Khách hàng"
    menu_order = 100
    search_backend_name = None  # tìm kiếm trực tiếp bằng QuerySet
    list_display = ["name", "email", "phone", "company", "status", "source", "ai_priority", "ai_sentiment", "assigned_staff", "created_at"]
    list_filter = ["status", "source", "ai_priority", "ai_sentiment", "assigned_staff"]
    search_fields = ["name", "email", "phone", "company"]
    panels = [
        MultiFieldPanel(
            [
                FieldPanel("name"),
                FieldRowPanel([FieldPanel("email"), FieldPanel("phone")]),
                FieldPanel("company"),
            ],
            heading="Thông tin liên hệ",
        ),
        MultiFieldPanel(
            [
                FieldRowPanel([FieldPanel("status"), FieldPanel("source")]),
                FieldPanel("assigned_staff"),
            ],
            heading="Quản lý",
        ),
        MultiFieldPanel(
            [
                FieldRowPanel([
                    FieldPanel("ai_sentiment", read_only=True),
                    FieldPanel("ai_priority", read_only=True),
                ]),
                FieldPanel("ai_suggested_status", read_only=True),
                FieldPanel("ai_summary", read_only=True),
                FieldPanel("ai_next_actions", read_only=True),
                FieldPanel("ai_analyzed_at", read_only=True),
            ],
            heading="Phân tích AI",
        ),
    ]


class OrderViewSet(SnippetViewSet):
    model = Order
    icon = "list-ul"
    menu_label = "Đơn hàng"
    menu_order = 200
    search_backend_name = None
    list_display = ["code", "customer", "status", "total_amount", "created_at"]
    list_filter = ["status", "customer"]
    search_fields = ["code", "customer__name", "customer__email", "note"]
    panels = [
        FieldRowPanel([FieldPanel("customer"), FieldPanel("status")]),
        FieldPanel("note"),
        InlinePanel("items", heading="Sản phẩm trong đơn", label="Dòng sản phẩm", min_num=1),
    ]


class InteractionLogViewSet(SnippetViewSet):
    model = InteractionLog
    icon = "mail"
    menu_label = "Lịch sử tương tác"
    menu_order = 300
    search_backend_name = None
    list_display = ["customer", "channel", "is_ai_generated", "staff", "created_at"]
    list_filter = ["channel", "is_ai_generated", "staff"]
    search_fields = ["customer__name", "customer_message", "final_reply"]
    panels = [
        FieldRowPanel([FieldPanel("customer"), FieldPanel("channel")]),
        FieldPanel("customer_message"),
        FieldPanel("ai_suggested_reply"),
        FieldPanel("final_reply"),
        FieldRowPanel([FieldPanel("is_ai_generated"), FieldPanel("staff")]),
    ]


class AIReportViewSet(SnippetViewSet):
    model = AIReport
    icon = "doc-full"
    menu_label = "Báo cáo AI"
    menu_order = 400
    search_backend_name = None
    list_display = ["__str__", "provider", "is_mock", "created_by", "created_at"]
    list_filter = ["is_mock", "provider"]
    search_fields = ["content"]
    panels = [
        FieldPanel("content", read_only=True),
        FieldPanel("stats", read_only=True),
        FieldRowPanel([
            FieldPanel("provider", read_only=True),
            FieldPanel("is_mock", read_only=True),
        ]),
        FieldRowPanel([
            FieldPanel("created_by", read_only=True),
            FieldPanel("created_at", read_only=True),
        ]),
    ]
    add_to_admin_menu = False
    inspect_view_enabled = True


class CRMViewSetGroup(SnippetViewSetGroup):
    menu_label = "CRM"
    menu_icon = "group"
    menu_order = 150
    items = (CustomerViewSet, OrderViewSet, InteractionLogViewSet, AIReportViewSet)


register_snippet(CRMViewSetGroup)


@hooks.register("register_admin_menu_item")
def register_smartcrm_menu_item():
    return MenuItem(
        "Mở SmartCRM",
        reverse("crm:dashboard"),
        name="open-smartcrm",
        icon_name="desktop",
        order=140,
    )
