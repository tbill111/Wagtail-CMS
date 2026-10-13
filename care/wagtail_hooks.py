from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.admin.ui.tables import BooleanColumn, Column
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import Campaign, CampaignMember, SupportTicket


class SupportTicketViewSet(SnippetViewSet):
    model = SupportTicket
    icon = "help"
    menu_label = "Phiếu hỗ trợ"
    menu_order = 100
    search_backend_name = None  # tìm kiếm trực tiếp bằng QuerySet
    list_display = [
        "code", "subject", "customer", "category", "priority", "status", "assigned_staff", "due_at",
        BooleanColumn("is_overdue", label="Quá hạn"), "created_at",
    ]
    list_filter = ["status", "priority", "category", "channel", "assigned_staff"]
    search_fields = ["code", "subject", "description", "customer__name", "customer__email"]
    panels = [
        MultiFieldPanel(
            [
                FieldRowPanel([FieldPanel("customer"), FieldPanel("order")]),
                FieldPanel("subject"),
                FieldPanel("description"),
                FieldRowPanel([FieldPanel("category"), FieldPanel("channel")]),
            ],
            heading="Yêu cầu của khách",
        ),
        MultiFieldPanel(
            [
                FieldRowPanel([FieldPanel("status"), FieldPanel("priority")]),
                FieldRowPanel([FieldPanel("assigned_staff"), FieldPanel("due_at")]),
            ],
            heading="Xử lý",
        ),
        InlinePanel("notes", heading="Nhật ký xử lý", label="Ghi chú xử lý", panels=[FieldPanel("content")]),
        MultiFieldPanel(
            [FieldPanel("resolution"), FieldPanel("satisfaction")],
            heading="Kết quả",
        ),
    ]


class CampaignViewSet(SnippetViewSet):
    model = Campaign
    icon = "site"
    menu_label = "Chiến dịch marketing"
    menu_order = 200
    search_backend_name = None
    list_display = [
        "name", "channel", "status", "start_date", "end_date",
        Column("member_count", label="Số khách"),
        Column("response_rate", label="Tỉ lệ phản hồi"),
        Column("conversion_rate", label="Tỉ lệ chuyển đổi"),
        Column("revenue", label="Doanh thu ghi nhận"),
        "budget",
    ]
    list_filter = ["status", "channel", "owner"]
    search_fields = ["name", "message"]
    panels = [
        MultiFieldPanel(
            [
                FieldPanel("name"),
                FieldRowPanel([FieldPanel("channel"), FieldPanel("status")]),
                FieldRowPanel([FieldPanel("start_date"), FieldPanel("end_date")]),
                FieldRowPanel([FieldPanel("budget"), FieldPanel("owner")]),
            ],
            heading="Thông tin chiến dịch",
        ),
        MultiFieldPanel(
            [FieldRowPanel([FieldPanel("target_status"), FieldPanel("target_source")])],
            heading="Khách hàng mục tiêu",
            help_text=(
                "Khi chiến dịch còn là Bản nháp, mỗi lần lưu hệ thống tự cập nhật danh sách khách khớp điều kiện. "
                "Từ khi Đang chạy, danh sách được giữ nguyên – thêm/bớt ở mục “Khách trong chiến dịch”."
            ),
        ),
        FieldPanel("message"),
    ]


class CampaignMemberViewSet(SnippetViewSet):
    model = CampaignMember
    icon = "group"
    menu_label = "Khách trong chiến dịch"
    menu_order = 300
    search_backend_name = None
    list_display = ["customer", "campaign", "response", "contacted_at", "note"]
    list_filter = ["campaign", "response"]
    search_fields = ["customer__name", "customer__email", "campaign__name", "note"]
    panels = [
        FieldRowPanel([FieldPanel("campaign"), FieldPanel("customer")]),
        FieldRowPanel([FieldPanel("response"), FieldPanel("contacted_at")]),
        FieldPanel("note"),
    ]


class CareViewSetGroup(SnippetViewSetGroup):
    menu_label = "Chăm sóc & Marketing"
    menu_icon = "pick"
    menu_order = 160  # ngay dưới nhóm CRM
    items = (SupportTicketViewSet, CampaignViewSet, CampaignMemberViewSet)


register_snippet(CareViewSetGroup)
