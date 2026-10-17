from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

import pandas as pd
from django.test import TestCase

from crm.models import Customer, Order, OrderItem
from insights.models import ModelRun
from insights.pipeline import forecast


class ForecastModuleTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Khách dự báo", email="forecast@example.com")

    def _series(self, months):
        index = pd.date_range("2023-01-01", periods=months, freq="MS")
        values = [100000 + (month % 12) * 25000 for month in range(months)]
        return pd.Series(values, index=index, dtype="int64", name="revenue")

    def _run(self, series):
        with mock.patch.object(forecast, "monthly_revenue_series", return_value=series):
            return forecast.run("forecast-test")

    def test_all_methods_write_contract_rows_and_select_one(self):
        runs = self._run(self._series(36))
        self.assertEqual({run.method for run in runs}, {"seasonal_naive", "holt_winters", "sarima"})
        self.assertTrue(all(run.status == ModelRun.Status.SUCCESS for run in runs))
        self.assertEqual(ModelRun.objects.filter(batch="forecast-test", is_selected=True).count(), 1)
        for run in runs:
            self.assertTrue({"mae", "rmse", "mape", "n_train", "n_test"} <= run.metrics.keys())
            self.assertEqual(run.forecasts.filter(kind="history").count(), 30)
            self.assertEqual(run.forecasts.filter(kind="backtest").count(), 6)
            self.assertEqual(run.forecasts.filter(kind="future").count(), 6)
            for row in run.forecasts.exclude(kind="history"):
                self.assertLessEqual(row.lower, row.forecast)
                self.assertLessEqual(row.forecast, row.upper)

    def test_short_series_succeeds_with_warning_notes(self):
        runs = self._run(self._series(14))
        self.assertEqual(len(runs), 3)
        self.assertTrue(all(run.status == ModelRun.Status.SUCCESS for run in runs))
        self.assertIn("Chưa đủ 12 tháng", runs[0].notes)

    def test_monthly_revenue_series_uses_completed_orders_and_full_months(self):
        def order(moment, amount, status=Order.Status.COMPLETED):
            item = OrderItem.objects.create(
                order=Order.objects.create(customer=self.customer, status=status),
                product_name="Sản phẩm", quantity=1, unit_price=amount,
            )
            Order.objects.filter(pk=item.order_id).update(created_at=moment)

        tz = ZoneInfo("Asia/Ho_Chi_Minh")
        order(datetime(2025, 1, 10, tzinfo=tz), 100)
        order(datetime(2025, 1, 20, tzinfo=tz), 999, Order.Status.CANCELLED)
        order(datetime(2025, 3, 5, tzinfo=tz), 300)
        order(datetime(2025, 4, 10, tzinfo=tz), 50)
        with mock.patch.object(forecast, "monthly_revenue_series", wraps=forecast.monthly_revenue_series) as helper:
            result = helper()
        self.assertEqual(result.tolist(), [100, 0, 300])
        self.assertEqual(list(result.index), list(pd.date_range("2025-01-01", "2025-03-01", freq="MS")))


class ForecastReviewFixTests(TestCase):
    """Các lỗi phát hiện khi review: metrics khớp dòng đã lưu, chặn SARIMA phân kỳ, MAPE không có tháng khác 0."""

    def _series(self, months):
        index = pd.date_range("2023-01-01", periods=months, freq="MS")
        values = [1_000_003 + (month % 12) * 250_007 + month * 1_111 for month in range(months)]
        return pd.Series(values, index=index, dtype="int64", name="revenue")

    def test_metrics_recomputable_from_saved_backtest_rows(self):
        with mock.patch.object(forecast, "monthly_revenue_series", return_value=self._series(30)):
            runs = forecast.run("forecast-recompute")
        for run in runs:
            rows = list(run.forecasts.filter(kind="backtest").order_by("month"))
            mae = sum(abs(float(row.actual - row.forecast)) for row in rows) / len(rows)
            self.assertAlmostEqual(mae, run.metrics["mae"], places=3, msg=run.method)

    def test_diverging_sarima_is_rejected_and_noted(self):
        class Exploding:
            def fit(self, disp=False):
                return self

            def get_forecast(self, horizon):
                values = pd.Series([10.0 ** (12 + step) for step in range(horizon)])
                return mock.Mock(predicted_mean=values,
                                 conf_int=lambda alpha: pd.DataFrame({"lo": values * 0.9, "hi": values * 1.1}))

        with mock.patch.object(forecast, "SARIMAX", return_value=Exploding()):
            prediction = forecast._sarima(self._series(30), 6, "backtest")
        self.assertIn("phân kỳ", " ".join(prediction.notes))
        self.assertLessEqual(max(prediction.values), 3 * self._series(30).max())

    def test_mape_is_none_when_all_actual_months_are_zero(self):
        self.assertIsNone(forecast._metrics([0, 0], [10, 20], 5)["mape"])

    def test_holt_winters_params_match_model_actually_used(self):
        short = forecast._holt_winters(self._series(18), 6, "backtest")
        self.assertEqual(short.params["model"], "additive_nonseasonal")
        self.assertIn("không dùng được mùa vụ", " ".join(short.notes))
        full = forecast._holt_winters(self._series(30), 6, "dự báo tới")
        self.assertEqual(full.params["model"], "additive_seasonal")
