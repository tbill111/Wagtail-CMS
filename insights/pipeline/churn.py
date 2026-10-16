"""Customer churn labels, features, evaluation, and scoring (TH2 checklist 02/05/06)."""

from datetime import datetime, time, timedelta

import pandas as pd
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Min, Q, Sum
from django.utils import timezone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from crm.models import InteractionLog, Order
from insights.conf import CHURN_WINDOW_DAYS, RANDOM_STATE, reference_date, risk_band
from insights.models import ChurnScore, ModelRun

from .base import MethodResult, run_method, select_best

FEATURES = [
    "recency_days",
    "frequency",
    "monetary",
    "avg_order_value",
    "tenure_days",
    "orders_last_90d",
    "cancelled_orders",
    "distinct_products",
    "interactions_count",
]
METHODS = ("rfm_rule", "logistic_regression", "random_forest")
def _local_start(day):
    """Start of a local calendar day as an aware datetime for DateTimeField filters."""
    return timezone.make_aware(datetime.combine(day, time.min), timezone.get_current_timezone())


def build_features(as_of_date):
    """Return one feature row per customer with a completed order by the end of as_of_date.

    Aggregation is done in a fixed number of ORM queries (not one query per customer).
    """
    if isinstance(as_of_date, datetime):
        as_of_date = timezone.localtime(as_of_date).date() if timezone.is_aware(as_of_date) else as_of_date.date()
    end = _local_start(as_of_date + timedelta(days=1))
    ninety_days_ago = _local_start(as_of_date - timedelta(days=89))
    completed = Order.objects.filter(status=Order.Status.COMPLETED, created_at__lt=end)

    order_rows = list(
        completed.values("customer_id").annotate(
            frequency=Count("pk", distinct=True),
            first_order=Min("created_at"),
            last_order=Max("created_at"),
            orders_last_90d=Count("pk", filter=Q(created_at__gte=ninety_days_ago), distinct=True),
            monetary=Sum(
                ExpressionWrapper(
                    F("items__quantity") * F("items__unit_price"),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
            distinct_products=(
                Count("items__product_id", distinct=True)
                + Count("items__product_name", filter=Q(items__product_id__isnull=True), distinct=True)
            ),
        )
    )
    if not order_rows:
        return pd.DataFrame(columns=FEATURES, index=pd.Index([], name="customer_id"), dtype=float)

    customer_ids = [row["customer_id"] for row in order_rows]
    cancelled = dict(
        Order.objects.filter(
            customer_id__in=customer_ids,
            status=Order.Status.CANCELLED,
            created_at__lt=end,
        ).values("customer_id").annotate(count=Count("pk")).values_list("customer_id", "count")
    )
    interactions = dict(
        InteractionLog.objects.filter(customer_id__in=customer_ids, created_at__lt=end)
        .values("customer_id").annotate(count=Count("pk")).values_list("customer_id", "count")
    )

    rows = []
    for order in order_rows:
        first = timezone.localtime(order["first_order"]).date()
        last = timezone.localtime(order["last_order"]).date()
        frequency = order["frequency"]
        monetary = float(order["monetary"] or 0)
        rows.append({
            "customer_id": order["customer_id"],
            "recency_days": (as_of_date - last).days,
            "frequency": frequency,
            "monetary": monetary,
            "avg_order_value": monetary / frequency if frequency else 0.0,
            "tenure_days": (as_of_date - first).days,
            "orders_last_90d": order["orders_last_90d"],
            "cancelled_orders": cancelled.get(order["customer_id"], 0),
            "distinct_products": order["distinct_products"] or 0,
            "interactions_count": interactions.get(order["customer_id"], 0),
        })
    return pd.DataFrame(rows).set_index("customer_id")[FEATURES].astype(float)


def build_labeled_data(reference=None):
    """Build point-in-time training features and binary churn labels for the reference date."""
    reference = reference or reference_date()
    cutoff = reference - timedelta(days=CHURN_WINDOW_DAYS)

    # The cutoff is a boundary: training features only include orders strictly before it.
    feature_frame = build_features(cutoff - timedelta(days=1))
    eligible_ids = set(
        Order.objects.filter(status=Order.Status.COMPLETED, created_at__lt=_local_start(cutoff))
        .values_list("customer_id", flat=True).distinct()
    )
    feature_frame = feature_frame.loc[feature_frame.index.intersection(list(eligible_ids))]
    if feature_frame.empty:
        return feature_frame, pd.Series(dtype=int, index=feature_frame.index), cutoff

    retained_ids = set(
        Order.objects.filter(
            status=Order.Status.COMPLETED,
            created_at__gt=_local_start(cutoff),
            created_at__lt=_local_start(reference + timedelta(days=1)),
        ).values_list("customer_id", flat=True).distinct()
    )
    labels = pd.Series(
        [0 if customer_id in retained_ids else 1 for customer_id in feature_frame.index],
        index=feature_frame.index,
        name="churned",
        dtype=int,
    )
    return feature_frame, labels, cutoff


def _metrics(y_true, probabilities, threshold_predictions, n_train, n_test):
    return {
        "auc": roc_auc_score(y_true, probabilities),
        "precision": precision_score(y_true, threshold_predictions, zero_division=0),
        "recall": recall_score(y_true, threshold_predictions, zero_division=0),
        "f1": f1_score(y_true, threshold_predictions, zero_division=0),
        "accuracy": accuracy_score(y_true, threshold_predictions),
        "confusion_matrix": confusion_matrix(y_true, threshold_predictions, labels=[0, 1]).tolist(),
        "churn_rate": float(pd.Series(y_true).mean()),
        "n_train": int(n_train),
        "n_test": int(n_test),
    }


def _new_model(method):
    if method == "logistic_regression":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=1000, random_state=RANDOM_STATE),
        )
    if method == "random_forest":
        return RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=RANDOM_STATE)
    raise ValueError(f"Không có bộ phân loại cho phương pháp {method}.")


def _rule_scores(frame):
    # Percentile rank of recency: the longer since the last purchase, the higher the risk.
    return frame["recency_days"].rank(method="average", pct=True).to_numpy()


def _make_method(method, train_x, test_x, y_train, y_test, all_x, scoring_x, batch_reference):
    def save_results(run):
        if method == "rfm_rule":
            test_probabilities = _rule_scores(test_x)
            all_probabilities = _rule_scores(scoring_x)
            params = {"formula": "percentile_rank(recency_days); older last purchase => higher score"}
        else:
            model = _new_model(method)
            model.fit(train_x, y_train)
            test_probabilities = model.predict_proba(test_x)[:, 1]
            model.fit(all_x, pd.concat([y_train, y_test]).loc[all_x.index])
            all_probabilities = model.predict_proba(scoring_x)[:, 1]
            params = {"class_weight": "balanced", "random_state": RANDOM_STATE}
            if method == "logistic_regression":
                params.update({"scaler": "StandardScaler", "max_iter": 1000})
            else:
                params.update({"n_estimators": 300})
                params["top_features"] = [
                    {"name": FEATURES[index], "importance": float(importance)}
                    for index, importance in sorted(
                        enumerate(model.feature_importances_), key=lambda item: item[1], reverse=True
                    )[:5]
                ]
        test_predictions = (test_probabilities >= 0.5).astype(int)
        metrics = _metrics(y_test, test_probabilities, test_predictions, len(train_x), len(test_x))
        scores = [
            ChurnScore(
                run=run,
                customer_id=customer_id,
                probability=float(probability),
                risk_band=risk_band(float(probability)),
            )
            for customer_id, probability in zip(scoring_x.index, all_probabilities)
        ]
        ChurnScore.objects.bulk_create(scores, batch_size=2000)
        params["reference_date"] = batch_reference.isoformat()
        return MethodResult(metrics=metrics, n_rows=len(scores), params=params)

    return save_results


def run(batch):
    reference = reference_date()
    features, labels, _cutoff = build_labeled_data(reference)
    if labels.empty:
        raise RuntimeError("Không có khách đủ điều kiện để tạo nhãn rời bỏ.")
    churn_rate = float(labels.mean())
    print(f"Tỷ lệ churn của tập: {churn_rate:.2%} ({int(labels.sum())}/{len(labels)} khách).")
    if churn_rate < 0.05 or churn_rate > 0.95:
        raise RuntimeError(
            f"Tỷ lệ rời bỏ {churn_rate:.1%} nằm ngoài khoảng 5%–95%; cần đối chiếu định nghĩa với nhóm TH2."
        )
    if labels.nunique() < 2:
        raise RuntimeError("Tập dữ liệu chỉ có một lớp nhãn, không thể huấn luyện mô hình.")

    train_ids, test_ids = train_test_split(
        features.index,
        test_size=0.30,
        random_state=RANDOM_STATE,
        stratify=labels,
    )
    train_x, test_x = features.loc[train_ids], features.loc[test_ids]
    y_train, y_test = labels.loc[train_ids], labels.loc[test_ids]
    scoring_x = build_features(reference)
    all_x = features

    runs = []
    for method in METHODS:
        func = _make_method(
            method, train_x, test_x, y_train, y_test, all_x, scoring_x, reference
        )
        runs.append(run_method(batch, ModelRun.Module.CHURN, method, func))
    selected = select_best(runs, "auc", higher_is_better=True)
    print("\nSo sánh phương pháp churn:")
    print(f"{'Phương pháp':<24} {'Trạng thái':<10} {'AUC':>8} {'Precision':>11} {'Recall':>8} {'F1':>8} {'Accuracy':>10}")
    for result in runs:
        metrics = result.metrics
        values = [metrics.get(key) for key in ("auc", "precision", "recall", "f1", "accuracy")]
        formatted = [f"{value:.4f}" if value is not None else "—" for value in values]
        marker = " ★" if result.is_selected else ""
        print(
            f"{result.method:<24} {result.status:<10} {formatted[0]:>8} {formatted[1]:>11} "
            f"{formatted[2]:>8} {formatted[3]:>8} {formatted[4]:>10}{marker}"
        )
    if selected:
        counts = dict(
            selected.churn_scores.values("risk_band").annotate(total=Count("pk"))
            .values_list("risk_band", "total")
        )
        print(
            "Số khách theo mức rủi ro (phương pháp được chọn): "
            f"cao={counts.get('high', 0)}, trung bình={counts.get('medium', 0)}, thấp={counts.get('low', 0)}."
        )
    else:
        print("Không có phương pháp thành công để chọn; chưa có phân bố mức rủi ro.")
    return runs
