"""Chạy các module AI và ghi kết quả vào app insights (TH2 · checklist 02).

    python manage.py run_ai_pipeline                     # mọi module đã có
    python manage.py run_ai_pipeline --only forecast churn

Mỗi lần chạy là một batch mới (YYYYMMDD-HHMMSS). Kết quả giả của seed_ai_demo (batch "demo") của ĐÚNG các module
được chạy bị xoá trước khi ghi; module chưa chạy giữ nguyên dữ liệu giả để dashboard vẫn có số.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from insights import pipeline
from insights.models import ModelRun

DEMO_BATCH = "demo"
MAIN_METRIC = {"forecast": "mape", "churn": "auc", "sentiment": "macro_f1"}


class Command(BaseCommand):
    help = "Chạy các mô hình AI (dự báo doanh thu, rời bỏ, cảm xúc) và lưu kết quả."

    def add_arguments(self, parser):
        parser.add_argument("--only", nargs="+", choices=list(pipeline.MODULES), help="Chỉ chạy các module này.")

    def handle(self, *args, **options):
        names = options["only"] or list(pipeline.MODULES)
        runners = {name: pipeline.load(name) for name in names}
        ready = [name for name, runner in runners.items() if runner]
        for name in names:
            if not runners[name]:
                self.stdout.write(self.style.WARNING(f"Bỏ qua '{name}': chưa có module {pipeline.MODULES[name]}."))
        if not ready:
            raise CommandError("Chưa có module AI nào để chạy.")

        deleted, _ = ModelRun.objects.filter(batch=DEMO_BATCH, module__in=ready).delete()
        if deleted:
            self.stdout.write(f"Đã xoá kết quả giả (batch '{DEMO_BATCH}') của: {', '.join(ready)}.")

        batch = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        self.stdout.write(f"Batch {batch}")
        failed = 0
        for name in ready:
            self.stdout.write(f"\n▶ {name}")
            runs = runners[name](batch)
            for run in runs:
                metric = MAIN_METRIC[name]
                value = run.metrics.get(metric)
                mark = "★" if run.is_selected else " "
                status = self.style.SUCCESS("OK ") if run.status == ModelRun.Status.SUCCESS else self.style.ERROR("LỖI")
                shown = "–" if value is None else value
                self.stdout.write(f"  {mark} {status} {run.method:<22} {metric}={shown:<10} {run.n_rows} dòng")
                if run.status != ModelRun.Status.SUCCESS:
                    failed += 1
                    self.stdout.write(f"      {run.notes.splitlines()[0]}")
        self.stdout.write("\n★ = phương pháp được chọn (is_selected).")
        if failed:
            self.stdout.write(self.style.WARNING(f"{failed} phương pháp lỗi – xem cột notes trong Admin › Kết quả AI."))
