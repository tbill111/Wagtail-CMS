"""Đối chiếu kết quả AI đã lưu với số liệu tự tính lại độc lập (TH2 · checklist 05) – Hoàng Hưng.

    python manage.py verify_ai_results                    # mọi module
    python manage.py verify_ai_results --module forecast  # một module

CHỈ ĐỌC – không ghi/xoá gì. Kiểm tra batch thành công mới nhất của từng module (bỏ qua batch "demo"):
  A. Chung     : đúng 1 phương pháp is_selected; đủ khoá metrics (HOP_DONG_DU_LIEU.md mục 5); chọn đúng tiêu chí.
  B. Dự báo    : actual khớp doanh thu tháng TỰ TÍNH LẠI (truy vấn riêng, không dùng insights.data); đủ 6 backtest +
                 6 future; lower ≤ forecast ≤ upper; MAE/RMSE/MAPE tính lại từ dòng backtest khớp metrics.
  C. Rời bỏ    : mọi khách đã mua đến reference_date đều có điểm; probability ∈ [0, 1]; risk_band đúng ngưỡng.
  D. Cảm xúc   : nhãn hợp lệ; accuracy và macro F1 tính lại từ SentimentResult ↔ SentimentLabel khớp metrics.
  E. View ai.* : số dòng mỗi view (PostgreSQL) khớp số dòng ORM của batch đó.
Thoát mã 1 nếu có mục LỆCH.
"""

import math
from collections import Counter
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from crm.models import Order, OrderItem
from insights.conf import BACKTEST_MONTHS, FORECAST_HORIZON, RISK_HIGH, RISK_MEDIUM, reference_date
from insights.models import ChurnScore, ModelRun, RevenueForecast, SentimentLabel, SentimentResult

DEMO = "demo"
REQUIRED = {
    "forecast": {"mae", "rmse", "mape", "n_train", "n_test"},
    "churn": {"auc", "precision", "recall", "f1", "accuracy", "confusion_matrix", "churn_rate", "n_train", "n_test"},
    "sentiment": {"accuracy", "macro_f1", "f1_by_class", "confusion_matrix", "n_eval", "avg_latency_ms"},
}
CRITERION = {"forecast": ("mape", min), "churn": ("auc", max), "sentiment": ("macro_f1", max)}
LABELS = ["positive", "neutral", "negative"]
VIEWS = {"forecast": "ai.revenue_forecast", "churn": "ai.churn_score", "sentiment": "ai.interaction_sentiment"}


class Report:
    def __init__(self, out, style):
        self.out, self.style, self.ok, self.bad = out, style, 0, 0

    def check(self, name, ok, detail=""):
        self.ok += bool(ok)
        self.bad += not ok
        mark = self.style.SUCCESS("KHỚP") if ok else self.style.ERROR("LỆCH")
        self.out.write(f"[{mark}] {name}" + (f"\n        {detail}" if detail else ""))
        return ok


def latest_batch(module):
    return (ModelRun.objects.filter(module=module, status=ModelRun.Status.SUCCESS).exclude(batch=DEMO)
            .order_by("-finished_at").values_list("batch", flat=True).first())


# ------------------------------------------------------------------ doanh thu tự tính lại (độc lập với insights.data)
def independent_monthly_revenue():
    """{date đầu tháng: doanh thu} – Σ quantity × unit_price đơn Hoàn thành, gom tháng theo giờ Việt Nam."""
    line = ExpressionWrapper(F("quantity") * F("unit_price"), output_field=DecimalField(max_digits=20, decimal_places=0))
    rows = (OrderItem.objects.filter(order__status=Order.Status.COMPLETED)
            .annotate(m=TruncMonth("order__created_at", tzinfo=timezone.get_current_timezone()))
            .values("m").annotate(total=Sum(line)))
    return {(r["m"].date() if hasattr(r["m"], "date") else r["m"]): int(r["total"]) for r in rows}


def recompute_forecast_metrics(rows):
    errors = [float(r.actual - r.forecast) for r in rows]
    nonzero = [(float(r.actual), e) for r, e in zip(rows, errors) if r.actual]
    return {
        "mae": sum(abs(e) for e in errors) / len(errors),
        "rmse": math.sqrt(sum(e * e for e in errors) / len(errors)),
        "mape": sum(abs(e / a) for a, e in nonzero) / len(nonzero) * 100 if nonzero else None,
    }


def recompute_sentiment(run):
    pairs = list(SentimentResult.objects.filter(run=run).values_list("label", "interaction__sentiment_label__label"))
    true_pred = [(t, p) for p, t in pairs if t]
    accuracy = sum(t == p for t, p in true_pred) / len(true_pred) if true_pred else 0
    f1s = []
    for label in LABELS:
        tp = sum(t == label and p == label for t, p in true_pred)
        fp = sum(t != label and p == label for t, p in true_pred)
        fn = sum(t == label and p != label for t, p in true_pred)
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return {"accuracy": accuracy, "macro_f1": sum(f1s) / len(f1s), "n": len(true_pred)}


def close(a, b, tol):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


class Command(BaseCommand):
    help = "Đối chiếu kết quả AI đã lưu với số liệu tính lại độc lập (chỉ đọc)."

    def add_arguments(self, parser):
        parser.add_argument("--module", choices=list(REQUIRED), help="Chỉ kiểm tra một module.")

    def handle(self, *args, **options):
        report = Report(self.stdout, self.style)
        modules = [options["module"]] if options["module"] else list(REQUIRED)
        for module in modules:
            batch = latest_batch(module)
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n▶ {module} – batch {batch or '(không có)'}"))
            if not batch:
                demo = ModelRun.objects.filter(module=module, batch=DEMO).exists()
                self.stdout.write(self.style.WARNING(
                    "  Chỉ có dữ liệu giả (batch 'demo') – chạy run_ai_pipeline để kiểm tra kết quả thật."
                    if demo else "  Chưa có kết quả nào – bỏ qua."))
                continue
            runs = list(ModelRun.objects.filter(module=module, batch=batch))
            self.check_common(report, module, runs)
            getattr(self, f"check_{module}")(report, [r for r in runs if r.status == ModelRun.Status.SUCCESS])
            self.check_view(report, module, batch, runs)

        total = report.ok + report.bad
        if report.bad:
            raise CommandError(f"{report.bad}/{total} mục LỆCH.")
        self.stdout.write(self.style.SUCCESS(f"\nTất cả {total} mục KHỚP."))

    # ---------------------------------------------------------------- A. chung
    def check_common(self, report, module, runs):
        selected = [r for r in runs if r.is_selected]
        report.check("A. Đúng 1 phương pháp được chọn", len(selected) == 1,
                     f"được chọn: {[r.method for r in selected]}")
        success = [r for r in runs if r.status == ModelRun.Status.SUCCESS]
        missing = {r.method: sorted(REQUIRED[module] - set(r.metrics)) for r in success}
        report.check("A. Đủ khoá metrics theo hợp đồng", not any(missing.values()),
                     "; ".join(f"{m}: thiếu {k}" for m, k in missing.items() if k) or f"{len(success)} phương pháp")
        metric, pick = CRITERION[module]
        candidates = [r for r in success if r.metrics.get(metric) is not None and not r.notes.startswith("[mô phỏng]")]
        if candidates and len(selected) == 1:
            best = pick(candidates, key=lambda r: r.metrics[metric])
            report.check(f"A. Chọn đúng theo {metric} ({pick.__name__})",
                         best.metrics[metric] == selected[0].metrics[metric],
                         f"được chọn {selected[0].method}={selected[0].metrics[metric]}, tốt nhất {best.method}="
                         f"{best.metrics[metric]}")

    # ---------------------------------------------------------------- B. dự báo
    def check_forecast(self, report, runs):
        revenue = independent_monthly_revenue()
        for run in runs:
            rows = list(run.forecasts.all())
            with_actual = [r for r in rows if r.kind in ("history", "backtest")]
            diffs = [abs(int(r.actual) - revenue.get(r.month, 0)) for r in with_actual]
            report.check(f"B. [{run.method}] actual khớp doanh thu tự tính ({len(with_actual)} tháng)",
                         bool(diffs) and max(diffs) <= 1, f"lệch lớn nhất {max(diffs, default=0):,} đ")
            backtest = sorted((r for r in rows if r.kind == "backtest"), key=lambda r: r.month)
            future = [r for r in rows if r.kind == "future"]
            report.check(f"B. [{run.method}] {BACKTEST_MONTHS} dòng backtest, {FORECAST_HORIZON} dòng future",
                         len(backtest) == BACKTEST_MONTHS and len(future) == FORECAST_HORIZON,
                         f"backtest={len(backtest)}, future={len(future)}")
            bad = [r.month for r in backtest + future if not (r.lower <= r.forecast <= r.upper)]
            report.check(f"B. [{run.method}] lower ≤ forecast ≤ upper", not bad, f"sai ở {bad}" if bad else "")
            if backtest:
                again = recompute_forecast_metrics(backtest)
                ok = all(close(again[k], run.metrics.get(k), 0.01) for k in ("mae", "rmse", "mape"))
                report.check(f"B. [{run.method}] MAE/RMSE/MAPE tính lại khớp metrics", ok,
                             "tính lại " + ", ".join(f"{k}={again[k]:,.4f}" for k in again)
                             + " | lưu " + ", ".join(f"{k}={run.metrics.get(k)}" for k in again))

    # ---------------------------------------------------------------- C. rời bỏ
    def check_churn(self, report, runs):
        ref = reference_date()
        until = timezone.make_aware(datetime.combine(ref + timedelta(days=1), time.min))
        buyers = set(Order.objects.filter(status=Order.Status.COMPLETED, created_at__lt=until)
                     .values_list("customer_id", flat=True).distinct())
        for run in runs:
            scores = list(run.churn_scores.values_list("customer_id", "probability", "risk_band"))
            scored = {pk for pk, _, _ in scores}
            report.check(f"C. [{run.method}] mọi khách đã mua đến {ref:%d/%m/%Y} đều có điểm",
                         scored == buyers, f"{len(scored)} có điểm / {len(buyers)} khách đã mua")
            out = sum(not 0 <= p <= 1 for _, p, _ in scores)
            report.check(f"C. [{run.method}] probability trong [0, 1]", out == 0, f"{out} giá trị ngoài khoảng")
            wrong = sum(band != ("high" if p >= RISK_HIGH else "medium" if p >= RISK_MEDIUM else "low")
                        for _, p, band in scores)
            counts = Counter(band for _, _, band in scores)
            report.check(f"C. [{run.method}] risk_band đúng ngưỡng {RISK_HIGH}/{RISK_MEDIUM}", wrong == 0,
                         f"Cao {counts['high']} · Trung bình {counts['medium']} · Thấp {counts['low']}"
                         + (f" · {wrong} sai" if wrong else ""))

    # ---------------------------------------------------------------- D. cảm xúc
    def check_sentiment(self, report, runs):
        for run in runs:
            invalid = SentimentResult.objects.filter(run=run).exclude(label__in=LABELS).count()
            report.check(f"D. [{run.method}] nhãn dự đoán hợp lệ", invalid == 0, f"{invalid} nhãn lạ")
            again = recompute_sentiment(run)
            ok = close(again["accuracy"], run.metrics.get("accuracy"), 0.001) and \
                close(again["macro_f1"], run.metrics.get("macro_f1"), 0.001)
            report.check(f"D. [{run.method}] accuracy, macro F1 tính lại khớp metrics ({again['n']} câu)", ok,
                         f"tính lại {again['accuracy']:.4f} / {again['macro_f1']:.4f} | lưu "
                         f"{run.metrics.get('accuracy')} / {run.metrics.get('macro_f1')}")
        unlabeled = SentimentResult.objects.filter(run__in=runs, interaction__sentiment_label__isnull=True).count()
        if unlabeled:
            self.stdout.write(self.style.WARNING(f"  {unlabeled} kết quả không có nhãn đúng – không tính vào D."))
        if not SentimentLabel.objects.exists():
            self.stdout.write(self.style.WARNING("  Chưa có SentimentLabel."))

    # ---------------------------------------------------------------- E. view ai.*
    def check_view(self, report, module, batch, runs):
        if connection.vendor != "postgresql":
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'ai'")
            if not cursor.fetchone():
                self.stdout.write(self.style.WARNING("  Chưa có schema ai – bỏ qua mục E."))
                return
            cursor.execute("SELECT count(*) FROM ai.model_run WHERE module = %s AND batch = %s", [module, batch])
            in_view = cursor.fetchone()[0]
            success = sum(r.status == ModelRun.Status.SUCCESS for r in runs)  # view chỉ lấy phương pháp thành công
            report.check("E. ai.model_run đúng số phương pháp của batch", in_view == success,
                         f"view {in_view} · ORM {success}")
            cursor.execute(f"SELECT count(*) FROM {VIEWS[module]} WHERE batch = %s", [batch])  # tên view cố định
            in_view = cursor.fetchone()[0]
        model = {"forecast": RevenueForecast, "churn": ChurnScore, "sentiment": SentimentResult}[module]
        in_orm = model.objects.filter(run__batch=batch, run__module=module, run__status=ModelRun.Status.SUCCESS).count()
        report.check(f"E. {VIEWS[module]} đúng số dòng của batch", in_view == in_orm, f"view {in_view} · ORM {in_orm}")
