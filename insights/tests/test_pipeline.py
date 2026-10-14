from datetime import date, datetime
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from crm.models import Customer, InteractionLog, Order, OrderItem
from insights import pipeline
from insights.conf import reference_date, risk_band
from insights.data import last_full_month, monthly_revenue_series
from insights.models import ChurnScore, ModelRun, RevenueForecast, SentimentLabel, SentimentResult
from insights.pipeline.base import MethodResult, round_metrics, run_method, select_best

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def make_order(customer, moment, amount, status=Order.Status.COMPLETED):
    order = Order.objects.create(customer=customer, status=status)
    OrderItem.objects.create(order=order, product_name="Hàng mẫu", quantity=1, unit_price=amount)
    Order.objects.filter(pk=order.pk).update(created_at=moment)
    return order


class DataHelperTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Khách A", email="a@example.com")

    def test_reference_date_is_latest_order_in_vietnam_time(self):
        make_order(self.customer, datetime(2025, 3, 31, 20, 0, tzinfo=ZoneInfo("UTC")), 100)  # 01/04 03:00 giờ VN
        self.assertEqual(reference_date(), date(2025, 4, 1))

    def test_last_full_month(self):
        self.assertEqual(last_full_month(date(2025, 4, 30)), date(2025, 4, 1))
        self.assertEqual(last_full_month(date(2025, 4, 29)), date(2025, 3, 1))
        self.assertEqual(last_full_month(date(2025, 1, 5)), date(2024, 12, 1))

    def test_monthly_series_counts_completed_only_fills_gaps_and_drops_partial_month(self):
        make_order(self.customer, datetime(2025, 1, 10, tzinfo=VN), 100)
        make_order(self.customer, datetime(2025, 1, 20, tzinfo=VN), 999, Order.Status.CANCELLED)
        make_order(self.customer, datetime(2025, 3, 5, tzinfo=VN), 300)
        make_order(self.customer, datetime(2025, 4, 10, tzinfo=VN), 50)  # tháng 4 chưa trọn → bỏ
        series = monthly_revenue_series()
        self.assertEqual([d.date() for d in series.index], [date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)])
        self.assertEqual(series.tolist(), [100, 0, 300])

    def test_risk_band_thresholds(self):
        self.assertEqual([risk_band(p) for p in (0.6, 0.59, 0.3, 0.29)], ["high", "medium", "medium", "low"])


class RunMethodTests(TestCase):
    def test_success_records_metrics_rounded(self):
        run = run_method("b1", "forecast", "m1", lambda run: MethodResult(metrics={"mape": 1.234567}, n_rows=3))
        self.assertEqual(run.status, ModelRun.Status.SUCCESS)
        self.assertEqual(run.metrics, {"mape": 1.2346})
        self.assertEqual(run.n_rows, 3)
        self.assertIsNotNone(run.finished_at)

    def test_failure_rolls_back_rows_and_keeps_going(self):
        def broken(run):
            RevenueForecast.objects.create(run=run, month=date(2025, 1, 1), kind="history", actual=1)
            raise ValueError("hỏng")

        with self.assertLogs("insights", "ERROR"):
            run = run_method("b1", "forecast", "m1", broken)
        self.assertEqual(run.status, ModelRun.Status.FAILED)
        self.assertIn("hỏng", run.notes)
        self.assertFalse(RevenueForecast.objects.exists())

    def test_select_best_marks_exactly_one_and_skips_failed_and_mock(self):
        ok = lambda value: (lambda run: MethodResult(metrics={"auc": value}, n_rows=0))  # noqa: E731
        with self.assertLogs("insights", "ERROR"):
            runs = [run_method("b", "churn", "a", ok(0.7)), run_method("b", "churn", "b", ok(0.9)),
                    run_method("b", "churn", "c", lambda run: 1 / 0)]
        mock_run = run_method("b", "churn", "d", lambda run: MethodResult({"auc": 0.99}, 0, notes="[mô phỏng] x"))
        best = select_best(runs + [mock_run], "auc", higher_is_better=True)
        self.assertEqual(best.method, "b")
        self.assertEqual(list(ModelRun.objects.filter(is_selected=True).values_list("method", flat=True)), ["b"])
        self.assertEqual(round_metrics({"x": [0.123456, {"y": 2.0}]}), {"x": [0.1235, {"y": 2.0}]})


class RunAiPipelineCommandTests(TestCase):
    def test_runs_available_modules_and_removes_demo_batch(self):
        ModelRun.objects.create(batch="demo", module="forecast", method="x", started_at=datetime.now(VN))

        def fake_run(batch):
            run = run_method(batch, "forecast", "seasonal_naive",
                             lambda run: MethodResult(metrics={"mape": 5.0}, n_rows=0))
            select_best([run], "mape", higher_is_better=False)
            return [run]

        out = StringIO()
        with mock.patch.object(pipeline, "load", side_effect=lambda name: fake_run if name == "forecast" else None):
            call_command("run_ai_pipeline", stdout=out)
        self.assertFalse(ModelRun.objects.filter(batch="demo").exists())
        self.assertTrue(ModelRun.objects.filter(module="forecast", is_selected=True).exists())
        self.assertIn("Bỏ qua 'churn'", out.getvalue())

    def test_error_when_no_module_available(self):
        with mock.patch.object(pipeline, "load", return_value=None), self.assertRaises(CommandError):
            call_command("run_ai_pipeline", stdout=StringIO())


class SeedAiDemoTests(TestCase):
    def test_demo_results_follow_contract_and_rerun_replaces(self):
        customer = Customer.objects.create(name="Khách B", email="b@example.com")
        for month in range(1, 13):
            make_order(customer, datetime(2024, month, 15, tzinfo=VN), 1000 * month)
        make_order(customer, datetime(2025, 1, 31, 23, tzinfo=VN), 500)
        log = InteractionLog.objects.create(customer=customer, customer_message="Máy tốt")
        SentimentLabel.objects.create(interaction=log, label="positive", source="test")

        call_command("seed_ai_demo", stdout=StringIO())
        call_command("seed_ai_demo", stdout=StringIO())

        runs = ModelRun.objects.filter(batch="demo")
        self.assertEqual(runs.count(), 8)
        for module in ("forecast", "churn", "sentiment"):
            self.assertEqual(runs.filter(module=module, is_selected=True).count(), 1)
        selected = runs.get(module="forecast", is_selected=True)
        kinds = {kind: selected.forecasts.filter(kind=kind).count() for kind in ("history", "backtest", "future")}
        self.assertEqual(kinds["backtest"], 6)
        self.assertEqual(kinds["future"], 6)
        self.assertEqual(ChurnScore.objects.filter(run__batch="demo").count(), 3)
        self.assertEqual(SentimentResult.objects.filter(run__batch="demo").count(), 2)
