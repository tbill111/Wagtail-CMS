from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from crm import analytics
from crm.management.commands.seed_superset import SAMPLE_DOMAIN
from crm.models import Customer, Order, Product


def seed(**options):
    call_command("seed_superset", customers=25, months=6, seed=7, stdout=StringIO(), **options)


class SeedSupersetTests(TestCase):
    def sample_customers(self):
        return Customer.objects.filter(email__endswith=f"@{SAMPLE_DOMAIN}")

    def test_creates_customers_orders_and_revenue(self):
        seed()
        self.assertEqual(self.sample_customers().count(), 25)
        self.assertTrue(Order.objects.filter(status=Order.Status.COMPLETED).exists())
        self.assertGreater(sum(m["value"] for m in analytics.monthly_revenue(12)), 0)

    def test_same_seed_gives_same_data(self):
        seed()
        first = sorted(self.sample_customers().values_list("email", "name", "status"))
        revenue = analytics.monthly_revenue(12)
        seed(reset=True)
        self.assertEqual(sorted(self.sample_customers().values_list("email", "name", "status")), first)
        self.assertEqual(analytics.monthly_revenue(12), revenue)

    def test_refuses_to_duplicate_without_reset(self):
        seed()
        with self.assertRaises(CommandError):
            seed()

    def test_stock_never_negative_and_some_products_run_low(self):
        seed()
        self.assertFalse(Product.objects.filter(stock__lt=0).exists())
        self.assertTrue(Product.low_stock().exists())

    def test_orders_are_backdated_after_customer_creation(self):
        seed()
        for order in Order.objects.filter(customer__in=self.sample_customers()).select_related("customer"):
            self.assertGreaterEqual(order.created_at, order.customer.created_at)
