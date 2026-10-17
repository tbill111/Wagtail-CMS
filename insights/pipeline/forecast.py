"""Forecasting methods for monthly revenue."""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from insights.conf import BACKTEST_MONTHS, FORECAST_HORIZON, RANDOM_STATE
from insights.data import monthly_revenue_series
from insights.models import ModelRun, RevenueForecast

from .base import MethodResult, run_method, select_best

METHODS = ("seasonal_naive", "holt_winters", "sarima")
Z_95 = 1.96
SIMULATIONS = 1000  # số lần mô phỏng để lấy khoảng tin cậy Holt-Winters
# Dự báo vượt quá MAX_GROWTH lần doanh thu tháng lớn nhất trong lịch sử → coi là mô hình phân kỳ
MAX_GROWTH = 3

logger = logging.getLogger("insights")


@dataclass
class Prediction:
    values: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    params: dict
    notes: list[str]


def _as_series(series):
    series = pd.Series(series, dtype="float64").copy()
    series.index = pd.DatetimeIndex(series.index).to_period("M").to_timestamp()
    return series.sort_index()


def _interval(values, error_std):
    values = np.maximum(np.asarray(values, dtype=float), 0)
    margin = Z_95 * (float(error_std) if np.isfinite(error_std) else 0)
    return values, np.maximum(values - margin, 0), values + margin


def _error_std(actual, predicted):
    errors = np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float)
    return float(np.std(errors, ddof=1)) if len(errors) > 1 else 0.0


def _seasonal_naive(series, horizon):
    values = np.asarray(series, dtype=float)
    notes = []
    if len(values) >= 12:
        predictions = np.array([values[-12 + i % 12] for i in range(horizon)])
        residuals = values[12:] - values[:-12]
    else:
        predictions = np.repeat(values[-1], horizon)
        residuals = np.diff(values)
        notes.append("Chưa đủ 12 tháng lịch sử, dùng doanh thu tháng liền trước.")
    forecast, lower, upper = _interval(predictions, _error_std(residuals, np.zeros_like(residuals)))
    return Prediction(
        forecast, lower, upper,
        {"lag": 12 if len(values) >= 12 else 1, "confidence": "forecast ± 1.96 × độ lệch chuẩn sai số"},
        notes,
    )


def _holt_winters(series, horizon, stage):
    """Thử Holt-Winters có mùa vụ trước; không chạy được (chuỗi < 2 chu kỳ) thì dùng bản chỉ có xu hướng."""
    notes = []
    try:
        model = ExponentialSmoothing(
            series, trend="add", seasonal="add", seasonal_periods=12,
            initialization_method="estimated",
        ).fit()
        predictions = np.asarray(model.forecast(horizon), dtype=float)
        fitted = np.asarray(model.fittedvalues, dtype=float)
        method = "additive_seasonal"
    except (ValueError, np.linalg.LinAlgError) as exc:
        notes.append(f"Holt-Winters ({stage}, {len(series)} tháng): không dùng được mùa vụ ({exc}); "
                     "dùng Holt không mùa vụ.")
        model = ExponentialSmoothing(
            series, trend="add", initialization_method="estimated",
        ).fit()
        predictions = np.asarray(model.forecast(horizon), dtype=float)
        fitted = np.asarray(model.fittedvalues, dtype=float)
        method = "additive_nonseasonal"
    try:
        # Khoảng tin cậy 95% bằng mô phỏng: rộng dần theo số bước dự báo, sát với mô hình hơn ±1,96σ cố định
        sims = np.asarray(model.simulate(horizon, repetitions=SIMULATIONS, error="add", random_state=RANDOM_STATE))
        lower, upper = np.percentile(sims.reshape(horizon, -1), [2.5, 97.5], axis=1)
        forecast = np.maximum(predictions, 0)
        lower = np.minimum(np.maximum(lower, 0), forecast)
        upper = np.maximum(upper, forecast)
        confidence = f"mô phỏng {SIMULATIONS} lần (simulate), phân vị 2,5% – 97,5%"
    except Exception as exc:  # noqa: BLE001 – mô phỏng lỗi thì quay về cách cũ, ghi lại lý do
        notes.append(f"Holt-Winters ({stage}): không mô phỏng được khoảng tin cậy ({exc}); dùng ±1,96σ sai số fitted.")
        forecast, lower, upper = _interval(predictions, _error_std(series, fitted))
        confidence = "forecast ± 1.96 × độ lệch sai số fitted"
    return Prediction(
        forecast, lower, upper,
        {"model": method, "trend": "add", "seasonal": "add" if method == "additive_seasonal" else None,
         "seasonal_periods": 12 if method == "additive_seasonal" else None,
         "confidence": confidence},
        notes,
    )


def _sarima(series, horizon, stage):
    notes = []
    limit = MAX_GROWTH * float(np.max(np.abs(np.asarray(series, dtype=float))))
    configs = []
    if len(series) >= 24:
        configs.append(((1, 1, 1), (0, 1, 1, 12)))
    else:
        configs.append(((1, 1, 1), (0, 1, 0, 12)))
        configs.append(((1, 1, 1), (0, 0, 0, 0)))
    last_error = None
    for order, seasonal_order in configs:
        try:
            model = SARIMAX(series, order=order, seasonal_order=seasonal_order).fit(disp=False)
            prediction = model.get_forecast(horizon)
            interval = prediction.conf_int(alpha=0.05)
            predictions = np.asarray(prediction.predicted_mean, dtype=float)
            if not np.all(np.isfinite(predictions)) or np.max(np.abs(predictions)) > limit:
                raise ValueError(f"dự báo phân kỳ (vượt {MAX_GROWTH} lần doanh thu tháng cao nhất)")
            lower = np.asarray(interval.iloc[:, 0], dtype=float)
            upper = np.asarray(interval.iloc[:, 1], dtype=float)
            predictions = np.maximum(predictions, 0)
            lower = np.maximum(lower, 0)
            upper = np.maximum(upper, predictions)
            if order != configs[0][0] or seasonal_order != configs[0][1] or len(series) < 24:
                notes.append(f"SARIMA ({stage}, {len(series)} tháng): dùng cấu hình {order}×{seasonal_order}.")
            return Prediction(
                predictions, np.minimum(lower, predictions), upper,
                {"order": order, "seasonal_order": seasonal_order,
                 "confidence": "statsmodels get_forecast().conf_int(alpha=0.05)"},
                notes,
            )
        except (ValueError, np.linalg.LinAlgError, TypeError, IndexError) as exc:
            last_error = exc
            notes.append(f"SARIMA {order}×{seasonal_order} bị loại: {str(exc).rstrip('.')}.")
    predictions = np.repeat(float(series.iloc[-1]), horizon)
    _, lower, upper = _interval(predictions, _error_std(np.asarray(series)[1:], np.asarray(series)[:-1]))
    notes.append(f"SARIMA ({stage}): không cấu hình nào dùng được ({last_error}); dùng mức tháng liền trước.")
    return Prediction(
        predictions, lower, upper,
        {"order": None, "seasonal_order": None,
         "confidence": "forecast ± 1.96 × độ lệch chuẩn sai số tháng liền trước"},
        notes,
    )


def _predict(method, series, horizon, backtest=False):
    stage = "backtest" if backtest else "dự báo tới"
    if method == "seasonal_naive":
        return _seasonal_naive(series, horizon)
    if method == "holt_winters":
        return _holt_winters(series, horizon, stage)
    if method == "sarima":
        return _sarima(series, horizon, stage)
    raise ValueError(f"Phương pháp không hợp lệ: {method}")


def _metrics(actual, forecast, n_train):
    actual = np.asarray(actual, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    errors = actual - forecast
    nonzero = actual != 0
    # Không có tháng doanh thu khác 0 thì không tính được MAPE (None – select_best bỏ qua, không chọn nhầm)
    mape = float(np.mean(np.abs(errors[nonzero] / actual[nonzero])) * 100) if nonzero.any() else None
    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "mape": mape,
        "n_train": int(n_train),
        "n_test": int(len(actual)),
    }


def _money(value):
    return int(round(max(float(value), 0)))


def _write_rows(run, history, test, backtest, future, future_index):
    RevenueForecast.objects.bulk_create(
        [RevenueForecast(run=run, month=month.date(), kind="history", actual=_money(value))
         for month, value in history.items()]
        + [RevenueForecast(run=run, month=month.date(), kind="backtest", actual=_money(actual),
                           forecast=_money(pred), lower=_money(low), upper=_money(high))
           for month, actual, pred, low, high in zip(test.index, test, backtest.values,
                                                      backtest.lower, backtest.upper)]
        + [RevenueForecast(run=run, month=month.date(), kind="future", forecast=_money(pred),
                           lower=_money(low), upper=_money(high))
           for month, pred, low, high in zip(future_index, future.values, future.lower, future.upper)]
    )


def _run_method(run, method, series):
    if len(series) <= BACKTEST_MONTHS:
        raise ValueError(f"Cần hơn {BACKTEST_MONTHS} tháng doanh thu để backtest.")
    history = series.iloc[:-BACKTEST_MONTHS]
    test = series.iloc[-BACKTEST_MONTHS:]
    backtest = _predict(method, history, len(test), backtest=True)
    future = _predict(method, series, FORECAST_HORIZON)
    notes = list(backtest.notes) + list(future.notes)
    _write_rows(run, history, test, backtest, future, pd.date_range(
        series.index[-1] + pd.offsets.MonthBegin(), periods=FORECAST_HORIZON, freq="MS"))
    # Tính trên đúng giá trị đã lưu (làm tròn đến đồng) để metrics tính lại được từ các dòng backtest
    metrics = _metrics(test, [_money(value) for value in backtest.values], len(history))
    if (test == 0).any():
        notes.append(f"Bỏ qua {(test == 0).sum()} tháng doanh thu thực tế bằng 0 khi tính MAPE.")
    return MethodResult(metrics=metrics, n_rows=len(history) + len(test) + FORECAST_HORIZON,
                        params={"backtest_months": BACKTEST_MONTHS, "forecast_horizon": FORECAST_HORIZON,
                                "money_unit": "VNĐ", "backtest": backtest.params, "future": future.params},
                        notes=" ".join(notes))


def run(batch: str) -> list[ModelRun]:
    series = _as_series(monthly_revenue_series())
    if series.empty:
        raise RuntimeError("Chưa có dữ liệu doanh thu. Chạy import_th2_data trước.")
    logger.info("Doanh thu: %s tháng, %s – %s, tổng %s VNĐ", len(series), series.index[0].date(),
                series.index[-1].date(), _money(series.sum()))
    runs = [
        run_method(batch, ModelRun.Module.FORECAST, method, lambda run, method=method: _run_method(run, method, series))
        for method in METHODS
    ]
    select_best(runs, "mape", higher_is_better=False)
    return runs
