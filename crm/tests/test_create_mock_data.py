from io import StringIO
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from crm.models import Customer, Order, OrderItem, Product


class CreateMockDataCommandTests(TestCase):
    def test_command_creates_mock_records(self):
        out = StringIO()

        call_command(
            "create_mock_data",
            customers=3,
            orders=2,
            interactions=4,
            reports=2,
            stdout=out,
        )

        self.assertEqual(Customer.objects.count(), 3)
        self.assertGreaterEqual(Order.objects.count(), 2)
        self.assertGreaterEqual(OrderItem.objects.count(), 2)
        self.assertGreaterEqual(Product.objects.count(), 1)

        order = Order.objects.first()
        self.assertIsNotNone(order)
        self.assertIsInstance(order.total_amount, Decimal)
        self.assertGreaterEqual(order.total_amount, Decimal("0"))
        self.assertIn("Hoàn tất: dữ liệu mock đã được tạo.", out.getvalue())
