from django.core.management import call_command
from django.test import TestCase

from crm.models import AIReport, Customer, InteractionLog, Order, OrderItem, Product


class CreateMockDataCommandTests(TestCase):
    def test_create_mock_data_generates_expected_records(self):
        call_command(
            "create_mock_data",
            customers=10,
            orders=20,
            interactions=30,
            reports=5,
            reset=True,
        )

        self.assertEqual(Customer.objects.count(), 10)
        self.assertEqual(Order.objects.count(), 20)
        self.assertEqual(InteractionLog.objects.count(), 30)
        self.assertEqual(AIReport.objects.count(), 5)
        self.assertGreaterEqual(OrderItem.objects.count(), 20)
        self.assertGreater(Product.objects.count(), 0)

    def test_order_total_amount_is_computed_from_items(self):
        call_command(
            "create_mock_data",
            customers=3,
            orders=3,
            interactions=3,
            reports=1,
            reset=True,
        )

        for order in Order.objects.all():
            self.assertGreaterEqual(order.total_amount, 0)
            self.assertEqual(
                sum(item.subtotal for item in order.items.all()),
                order.total_amount,
            )
