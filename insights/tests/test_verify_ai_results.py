import json
from datetime import datetime
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from crm.models import Customer, InteractionLog, Order, OrderItem
from crm.services.ai_service import GeminiCRMService
from insights.models import ModelRun, SentimentLabel
from insights.pipeline import churn, forecast, sentiment

BATCH = "20250101-000000"


def verify(**options):
    out = StringIO()
    call_command("verify_ai_results", stdout=out, **options)
    return out.getvalue()


def add_order(customer, when, amount, status=Order.Status.COMPLETED):
    order = Order.objects.create(customer=customer, status=status)
    OrderItem.objects.create(order=order, product_name=f"SP{amount % 5}", quantity=1, unit_price=amount)
    Order.objects.filter(pk=order.pk).update(created_at=timezone.make_aware(when))


def fake_ai(prompt, json_schema=None, temperature=0.7):
    """AI giả: trả "positive" cho mọi câu trong lô (đủ để có 2 phương pháp cảm xúc thật, không gọi mạng)."""
    count = prompt.count("\n[")
    return json.dumps({"results": [{"id": i, "label": "positive", "confidence": 0.9} for i in range(count)]})


class VerifyAIResultsTests(TestCase):
    """Dữ liệu giả nhỏ: 30 tháng doanh thu, 30 khách có nhãn rời bỏ rõ ràng, 6 tin nhắn có nhãn cảm xúc."""

    def setUp(self):
        shop = Customer.objects.create(name="Khách sỉ", email="si@example.com")
        year, month = 2023, 1
        for index in range(30):
            add_order(shop, datetime(year, month, 15, 10), 100_000_000 + 3_000_000 * index + (index % 12) * 5_000_000)
            year, month = (year, month + 1) if month < 12 else (year + 1, 1)
        for i in range(15):
            loyal = Customer.objects.create(name=f"Trung thành {i}", email=f"l{i}@example.com")
            for m in range(1, 12, 2):
                add_order(loyal, datetime(2025, m, 5 + i % 10), 200_000 + i * 1000)
            add_order(loyal, datetime(2025, 12, 1 + i % 10), 150_000)
            lost = Customer.objects.create(name=f"Bỏ đi {i}", email=f"b{i}@example.com")
            add_order(lost, datetime(2024, 11 + i % 2, 3 + i), 90_000)
            add_order(lost, datetime(2025, 2, 2), 80_000, status=Order.Status.CANCELLED)
        add_order(shop, datetime(2025, 12, 31, 12), 1)  # đơn muộn nhất → reference_date 31/12/2025
        texts = [("Rất tốt, hài lòng", "positive"), ("Tệ quá, thất vọng", "negative"), ("Mua cho mẹ", "neutral")]
        for text, label in texts * 2:
            log = InteractionLog.objects.create(customer=shop, customer_message=text)
            SentimentLabel.objects.create(interaction=log, label=label, source="test")

    @override_settings(AI_MOCK=False, GEMINI_API_KEY="test-key")
    def run_all(self):
        forecast.run(BATCH)
        churn.run(BATCH)
        with mock.patch.object(sentiment, "SENTIMENT_SAMPLE", 0), \
                mock.patch.object(GeminiCRMService, "_generate", side_effect=fake_ai):
            sentiment.run(BATCH)

    def test_everything_matches(self):
        self.run_all()
        output = verify()
        self.assertNotIn("LỆCH", output)
        for section in ("A. ", "B. ", "C. ", "D. "):
            self.assertIn(section, output)
        self.assertIn("Tất cả", output)

    def test_wrong_metric_is_reported_and_exits_with_error(self):
        self.run_all()
        run = ModelRun.objects.get(batch=BATCH, module="forecast", method="sarima")
        run.metrics["mae"] = run.metrics["mae"] + 5
        run.save()
        with self.assertRaisesMessage(CommandError, "LỆCH"):
            verify(module="forecast")

    def test_wrong_selection_is_reported(self):
        self.run_all()
        ModelRun.objects.filter(batch=BATCH, module="churn").update(is_selected=True)
        with self.assertRaises(CommandError):
            verify(module="churn")

    def test_demo_batch_is_ignored_and_only_demo_gives_warning(self):
        call_command("seed_ai_demo", stdout=StringIO())
        output = verify()
        self.assertIn("Chỉ có dữ liệu giả", output)
        self.assertIn("Tất cả 0 mục KHỚP", output)
        self.run_all()  # có batch thật → batch demo bị bỏ qua, không làm lệch mục A
        self.assertNotIn("LỆCH", verify())
