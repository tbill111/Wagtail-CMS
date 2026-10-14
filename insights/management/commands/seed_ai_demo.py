"""Ghi kết quả AI GIẢ (batch "demo") đúng cấu trúc hợp đồng dữ liệu, để dựng dashboard trước khi mô hình thật xong.

    python manage.py seed_ai_demo

Chạy lại được nhiều lần (xoá batch demo cũ). run_ai_pipeline tự xoá batch demo khi ghi kết quả thật.
Doanh thu thực tế là số thật từ CSDL; dự báo, xác suất rời bỏ, nhãn cảm xúc là số ngẫu nhiên.
"""

import random
from decimal import Decimal

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm.analytics import COMPLETED_ITEMS
from crm.models import Customer, OrderItem
from insights.conf import BACKTEST_MONTHS, FORECAST_HORIZON, RANDOM_STATE, risk_band
from insights.data import monthly_revenue_series
from insights.pipeline.base import round_metrics
from insights.models import ChurnScore, ModelRun, RevenueForecast, SentimentLabel, SentimentResult

DEMO_BATCH = "demo"
NOTE = "Dữ liệu giả của seed_ai_demo – chỉ để dựng dashboard."
METHODS = {
    "forecast": ["seasonal_naive", "holt_winters", "sarima"],
    "churn": ["rfm_rule", "logistic_regression", "random_forest"],
    "sentiment": ["keyword", "gemini"],
}
LABELS = ["positive", "neutral", "negative"]


class Command(BaseCommand):
    help = "Ghi kết quả AI giả (batch demo) để dựng dashboard."

    def handle(self, *args, **options):
        rng = random.Random(RANDOM_STATE)
        with transaction.atomic():
            ModelRun.objects.filter(batch=DEMO_BATCH).delete()
            counts = {
                "forecast": self.seed_forecast(rng),
                "churn": self.seed_churn(rng),
                "sentiment": self.seed_sentiment(rng),
            }
        for module, n in counts.items():
            self.stdout.write(f"  {module:<10} {n} dòng")
        self.stdout.write(self.style.SUCCESS(f"Đã ghi kết quả giả vào batch '{DEMO_BATCH}'."))

    def make_run(self, module, method, selected, metrics, n_rows):
        now = timezone.now()
        return ModelRun.objects.create(
            batch=DEMO_BATCH, module=module, method=method, is_selected=selected, started_at=now,
            finished_at=now, n_rows=n_rows, metrics=round_metrics(metrics), notes=NOTE,
        )

    def seed_forecast(self, rng):
        series = monthly_revenue_series()
        if len(series) < BACKTEST_MONTHS + 1:
            months = pd.date_range("2024-01-01", periods=30, freq="MS")
            series = pd.Series([rng.randint(800, 1500) * 1_000_000 for _ in months], index=months)
        history, test = series.iloc[:-BACKTEST_MONTHS], series.iloc[-BACKTEST_MONTHS:]
        future = pd.date_range(series.index[-1] + pd.offsets.MonthBegin(), periods=FORECAST_HORIZON, freq="MS")
        total = 0
        for i, method in enumerate(METHODS["forecast"]):
            error = 0.05 + 0.05 * i
            rows = [RevenueForecast(month=m.date(), kind="history", actual=Decimal(int(v))) for m, v in history.items()]
            for m, v in test.items():
                pred = int(v * (1 + rng.uniform(-error, error)))
                rows.append(RevenueForecast(month=m.date(), kind="backtest", actual=Decimal(int(v)),
                                            forecast=pred, lower=int(pred * 0.85), upper=int(pred * 1.15)))
            base = float(series.iloc[-12:].mean())
            for m in future:
                pred = int(base * (1 + rng.uniform(-0.1, 0.1)))
                rows.append(RevenueForecast(month=m.date(), kind="future", forecast=pred,
                                            lower=int(pred * 0.8), upper=int(pred * 1.2)))
            run = self.make_run("forecast", method, i == 0, {
                "mae": round(float(test.mean()) * error, 4), "rmse": round(float(test.mean()) * error * 1.2, 4),
                "mape": round(error * 100, 4), "n_train": len(history), "n_test": len(test),
            }, len(rows))
            for row in rows:
                row.run = run
            RevenueForecast.objects.bulk_create(rows)
            total += len(rows)
        return total

    def seed_churn(self, rng):
        buyers = list(Customer.objects.filter(
            pk__in=OrderItem.objects.filter(COMPLETED_ITEMS).values("order__customer")).values_list("pk", flat=True))
        total = 0
        for i, method in enumerate(METHODS["churn"]):
            run = self.make_run("churn", method, i == 2, {
                "auc": 0.70 + 0.05 * i, "precision": 0.6, "recall": 0.65, "f1": 0.62, "accuracy": 0.7,
                "confusion_matrix": [[100, 30], [25, 60]], "churn_rate": 0.4, "n_train": 500, "n_test": 215,
            }, len(buyers))
            rows = []
            for pk in buyers:
                p = round(rng.betavariate(2, 3), 4)
                rows.append(ChurnScore(run=run, customer_id=pk, probability=p, risk_band=risk_band(p)))
            ChurnScore.objects.bulk_create(rows, batch_size=2000)
            total += len(rows)
        return total

    def seed_sentiment(self, rng):
        labelled = list(SentimentLabel.objects.values_list("interaction_id", "label"))
        total = 0
        for i, method in enumerate(METHODS["sentiment"]):
            hit = 0.6 + 0.2 * i
            run = self.make_run("sentiment", method, i == 1, {
                "accuracy": hit, "macro_f1": hit - 0.05, "f1_by_class": {k: hit for k in LABELS},
                "confusion_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "n_eval": len(labelled),
                "avg_latency_ms": 2 if i == 0 else 900,
            }, len(labelled))
            rows = [SentimentResult(run=run, interaction_id=pk,
                                    label=true if rng.random() < hit else rng.choice(LABELS))
                    for pk, true in labelled]
            SentimentResult.objects.bulk_create(rows, batch_size=2000)
            total += len(rows)
        return total
