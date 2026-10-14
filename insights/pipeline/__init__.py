"""Danh sách module AI của run_ai_pipeline. Mỗi module là file ``<tên>.py`` có hàm ``run(batch) -> list[ModelRun]``.

Thêm module mới: thêm đúng 1 dòng vào MODULES (docs/th2/HOP_DONG_DU_LIEU.md mục 6).
"""

from importlib import import_module

MODULES = {
    "forecast": "insights.pipeline.forecast",    # Ngọc Anh
    "churn": "insights.pipeline.churn",          # Thái Anh
    "sentiment": "insights.pipeline.sentiment",  # Tùng
}


def load(name):
    """Hàm ``run`` của module, hoặc None nếu module chưa được viết."""
    try:
        module = import_module(MODULES[name])
    except ModuleNotFoundError as exc:
        if exc.name == MODULES[name]:
            return None
        raise
    return module.run
