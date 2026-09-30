from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.admin.ui.tables import BooleanColumn
from wagtail.permission_policies.base import ModelPermissionPolicy
from wagtail.permissions import register_permission_policy
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
                FieldRowPanel([
                    FieldPanel("ai_analyzed_at", read_only=True),
                    FieldPanel("ai_provider", read_only=True),
                ]),
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


class ReadOnlyPermissionPolicy(ModelPermissionPolicy):
    """Chỉ cho xem: không ai (kể cả superuser) được thêm/sửa/xoá qua Admin."""

    blocked_actions = {"add", "change", "delete"}

    def user_has_permission(self, user, action):
        if action in self.blocked_actions:
            return False
        return super().user_has_permission(user, action)

    def users_with_any_permission(self, actions):
        return super().users_with_any_permission(set(actions) - self.blocked_actions)


# AIReport chỉ được tạo từ trang /crm/reports/ (luồng AI → CSDL → Admin)
register_permission_policy(AIReport, ReadOnlyPermissionPolicy(AIReport))


class AIReportViewSet(SnippetViewSet):
    model = AIReport
    icon = "doc-full"
    menu_label = "Báo cáo AI"
    menu_order = 400
    search_backend_name = None
    list_display = ["__str__", "provider", BooleanColumn("is_mock", label="Chế độ mô phỏng"), "created_by", "created_at"]
    list_filter = ["is_mock", "provider"]
    search_fields = ["content"]
    inspect_view_enabled = True
    inspect_view_fields = ["content", "stats", "provider", "is_mock", "created_by", "created_at"]


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
