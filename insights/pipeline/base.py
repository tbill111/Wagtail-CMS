"""Hàm dùng chung cho các module AI: ghi ModelRun, bắt lỗi từng phương pháp, chọn phương pháp tốt nhất."""

import logging
import traceback
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from insights.models import ModelRun

logger = logging.getLogger("insights")


@dataclass
class MethodResult:
    """Giá trị mà hàm của một phương pháp trả về cho ``run_method``."""

    metrics: dict
    n_rows: int
    params: dict = field(default_factory=dict)
    notes: str = ""


def round_metrics(metrics, digits=4):
    """Làm tròn mọi số thực (kể cả trong dict/list lồng nhau) theo quy ước 4 chữ số."""
    if isinstance(metrics, float):
        return round(metrics, digits)
    if isinstance(metrics, dict):
        return {key: round_metrics(value, digits) for key, value in metrics.items()}
    if isinstance(metrics, (list, tuple)):
        return [round_metrics(value, digits) for value in metrics]
    return metrics


def run_method(batch, module, method, func):
    """Chạy ``func(run)`` cho một phương pháp; ``func`` ghi các dòng kết quả gắn với ``run`` và trả về MethodResult.

    Lỗi ở một phương pháp không làm dừng phương pháp khác: dòng kết quả bị huỷ, ModelRun ghi status="failed".
    """
    run = ModelRun.objects.create(batch=batch, module=module, method=method, started_at=timezone.now())
    try:
        with transaction.atomic():
            result = func(run)
            run.metrics = round_metrics(result.metrics)
            run.params = result.params
            run.n_rows = result.n_rows
            run.notes = result.notes
            run.status = ModelRun.Status.SUCCESS
            run.finished_at = timezone.now()
            run.save()
    except Exception as exc:  # noqa: BLE001 – ghi lại mọi lỗi để báo cáo, không dừng pipeline
        logger.exception("Phương pháp %s/%s lỗi", module, method)
        run.status = ModelRun.Status.FAILED
        run.notes = f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc(limit=3)}"
        run.finished_at = timezone.now()
        run.save()
    return run


def select_best(runs, metric, higher_is_better):
    """Đánh dấu is_selected cho đúng 1 run thành công có ``metric`` tốt nhất. Trả về run được chọn (hoặc None).

    Run có ghi chú bắt đầu bằng "[mô phỏng]" không được chọn.
    """
    candidates = [
        run for run in runs
        if run.status == ModelRun.Status.SUCCESS and run.metrics.get(metric) is not None
        and not run.notes.startswith("[mô phỏng]")
    ]
    if not candidates:
        return None
    best = (max if higher_is_better else min)(candidates, key=lambda run: run.metrics[metric])
    ModelRun.objects.filter(pk__in=[run.pk for run in runs]).update(is_selected=False)
    ModelRun.objects.filter(pk=best.pk).update(is_selected=True)
    for run in runs:
        run.is_selected = run.pk == best.pk
    return best
