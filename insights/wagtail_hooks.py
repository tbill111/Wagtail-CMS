from wagtail.admin.ui.tables import BooleanColumn
from wagtail.permissions import register_permission_policy
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from crm.wagtail_hooks import ReadOnlyPermissionPolicy

from .models import ModelRun

# Kết quả AI chỉ do run_ai_pipeline ghi – Admin chỉ để xem
register_permission_policy(ModelRun, ReadOnlyPermissionPolicy(ModelRun))


class ModelRunViewSet(SnippetViewSet):
    model = ModelRun
    icon = "pick"
    menu_label = "Kết quả AI"
    menu_order = 160
    add_to_admin_menu = True
    search_backend_name = None
    list_display = ["batch", "module", "method", BooleanColumn("is_selected", label="Được chọn"), "status",
                    "n_rows", "finished_at"]
    list_filter = ["module", "status", "is_selected"]
    search_fields = ["batch", "method"]
    inspect_view_enabled = True
    inspect_view_fields = ["batch", "module", "method", "is_selected", "status", "started_at", "finished_at",
                           "n_rows", "metrics", "params", "notes"]


register_snippet(ModelRunViewSet)
