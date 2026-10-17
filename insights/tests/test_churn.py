from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from crm.models import Customer, InteractionLog, Order, OrderItem
from insights.conf import CHURN_WINDOW_DAYS, risk_band
from insights.models import ChurnScore, ModelRun
from insights.pipeline.churn import FEATURES, build_features, build_labeled_data, run

VN = ZoneInfo("Asia/Ho_Chi_Minh")
REFERENCE = date(2025, 12, 31)


def add_order(customer, order_date, amount=10000, status=Order.Status.COMPLETED, product="Sản phẩm A"):
    order = Order.objects.create(customer=customer, status=status)
    OrderItem.objects.create(
        order=order,
        product_name=product,
        quantity=1,
        unit_price=Decimal(amount),
    )
    Order.objects.filter(pk=order.pk).update(
        created_at=datetime.combine(order_date, datetime.min.time(), tzinfo=VN)
    )
    return order


class ChurnFixtureMixin:
    def create_population(self):
        self.customers = []
        cutoff = REFERENCE - timedelta(days=CHURN_WINDOW_DAYS)
        for index in range(20):
            customer = Customer.objects.create(name=f"Khách {index}", email=f"c{index}@example.com")
            add_order(customer, date(2025, 1, 10), amount=10000 + index * 1000, product=f"Mặt hàng {index % 4}")
            if index % 2:
                add_order(customer, cutoff + timedelta(days=20 + index), amount=15000, product="Mặt hàng mới")
            self.customers.append(customer)
        return cutoff


class ChurnLabelAndFeatureTests(ChurnFixtureMixin, TestCase):
    def test_label_matches_cutoff_window(self):
        cutoff = self.create_population()
        add_order(self.customers[0], cutoff, amount=25000, product="Đơn tại mốc cutoff")
        features, labels, actual_cutoff = build_labeled_data(REFERENCE)

        self.assertEqual(actual_cutoff, cutoff)
        self.assertEqual(len(features), 20)
        self.assertEqual(set(labels.unique()), {0, 1})
        self.assertEqual(labels.loc[self.customers[0].pk], 1)
        self.assertEqual(labels.loc[self.customers[1].pk], 0)
        self.assertEqual(labels.loc[self.customers[2].pk], 1)

    def test_features_stop_before_cutoff_and_include_required_columns(self):
        cutoff = self.create_population()
        target = self.customers[0]
        add_order(target, cutoff + timedelta(days=4), amount=999999, product="Tương lai")
        InteractionLog.objects.create(customer=target, customer_message="Tương tác sau cutoff")

        features, labels, _ = build_labeled_data(REFERENCE)
        row = features.loc[target.pk]
        self.assertEqual(list(features.columns), FEATURES)
        self.assertEqual(row["frequency"], 1)
        self.assertEqual(row["monetary"], 10000)
        self.assertEqual(row["tenure_days"], (cutoff - timedelta(days=1) - date(2025, 1, 10)).days)
        self.assertEqual(row["interactions_count"], 0)
        self.assertEqual(labels.loc[target.pk], 1)


class ChurnPipelineTests(ChurnFixtureMixin, TestCase):
    def test_three_methods_save_metrics_scores_and_one_selection(self):
        self.create_population()
        runs = run("churn-test-batch")

        self.assertEqual({item.method for item in runs}, {"rfm_rule", "logistic_regression", "random_forest"})
        successful = [item for item in runs if item.status == ModelRun.Status.SUCCESS]
        self.assertEqual(len(successful), 3)
        self.assertEqual(sum(item.is_selected for item in runs), 1)
        required = {
            "auc", "precision", "recall", "f1", "accuracy", "confusion_matrix", "churn_rate", "n_train", "n_test",
        }
        for item in successful:
            self.assertEqual(set(item.metrics), required)
            scores = list(ChurnScore.objects.filter(run=item))
            self.assertEqual(len(scores), 20)
            self.assertTrue(all(0 <= score.probability <= 1 for score in scores))
            self.assertTrue(all(score.risk_band == risk_band(score.probability) for score in scores))
        forest = next(item for item in successful if item.method == "random_forest")
        self.assertEqual(len(forest.params["top_features"]), 5)


class ChurnRiskPageTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.staff = get_user_model().objects.create_user("staff", password="pass", is_staff=True)
        self.customer = Customer.objects.create(name="Khách xem", email="view@example.com")
        self.client.force_login(self.staff)
        self.url = reverse("crm:customer_detail", args=[self.customer.pk])

    def test_detail_shows_score_from_selected_successful_run(self):
        run_row = ModelRun.objects.create(
            batch="churn-view",
            module=ModelRun.Module.CHURN,
            method="random_forest",
            is_selected=True,
            status=ModelRun.Status.SUCCESS,
            started_at=datetime(2025, 12, 31, tzinfo=VN),
            finished_at=datetime(2025, 12, 31, tzinfo=VN),
        )
        ChurnScore.objects.create(run=run_row, customer=self.customer, probability=0.78, risk_band="high")

        response = self.client.get(self.url)

        self.assertContains(response, "Rủi ro rời bỏ")
        self.assertContains(response, "78% – Cao")
        self.assertContains(response, "Mô hình Rừng ngẫu nhiên")

    def test_detail_shows_empty_state_without_a_score(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Chưa có dự đoán")
