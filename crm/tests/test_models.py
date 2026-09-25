from datetime import date
from decimal import Decimal

from django.test import TestCase

from crm.models import InteractionLog, Order, OrderItem

from .factories import make_customer, make_order


class OrderCodeTests(TestCase):
    def test_code_is_generated_with_expected_format(self):
        order = make_order(make_customer())
        self.assertRegex(order.code, r"^DH-\d{8}-0001$")

    def test_code_increments_within_same_day(self):
        customer = make_customer()
        first = make_order(customer)
        second = make_order(customer)
        self.assertEqual(first.code[:12], second.code[:12])
        self.assertEqual(int(second.code[-4:]), int(first.code[-4:]) + 1)

    def test_generate_code_for_given_date(self):
        self.assertEqual(Order.generate_code(date(2026, 1, 5)), "DH-20260105-0001")


class AmountTests(TestCase):
    def test_orderitem_subtotal(self):
        item = OrderItem(product_name="X", quantity=3, unit_price=Decimal("250000"))
        self.assertEqual(item.subtotal, Decimal("750000"))

    def test_order_total_amount(self):
        order = make_order(make_customer(), items=[("A", 2, 100000), ("B", 1, 50000)])
        self.assertEqual(order.total_amount, Decimal("250000"))

    def test_customer_total_spent_counts_only_completed_orders(self):
        customer = make_customer()
        make_order(customer, Order.Status.COMPLETED, [("A", 1, 300000)])
        make_order(customer, Order.Status.COMPLETED, [("B", 2, 100000)])
        make_order(customer, Order.Status.CANCELLED, [("C", 1, 999000)])
        make_order(customer, Order.Status.NEW, [("D", 1, 111000)])
        self.assertEqual(customer.total_spent, Decimal("500000"))

    def test_total_spent_is_zero_without_orders(self):
        self.assertEqual(make_customer().total_spent, Decimal("0"))


class InteractionLogTests(TestCase):
    def test_default_ordering_newest_first(self):
        customer = make_customer()
        old = InteractionLog.objects.create(customer=customer, customer_message="Cũ")
        new = InteractionLog.objects.create(customer=customer, customer_message="Mới")
        self.assertEqual(list(customer.interactions.all()), [new, old])
