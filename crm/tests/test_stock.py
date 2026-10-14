import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from crm import analytics
from crm.models import InsufficientStockError, Order, OrderItem, Product

from .factories import make_customer


def make_product(sku="SP-01", stock=10, min_stock=2, price=100000, track_stock=True, **kwargs):
    return Product.objects.create(
        sku=sku, name=kwargs.pop("name", f"Sản phẩm {sku}"), price=Decimal(price),
        stock=stock, min_stock=min_stock, track_stock=track_stock, **kwargs,
    )


def make_stock_order(customer, status, lines):
    order = Order(
        customer=customer, status=status,
        items=[OrderItem(product=product, quantity=quantity) for product, quantity in lines],
    )
    order.save()
    return order


def stock_of(product):
    product.refresh_from_db()
    return product.stock


class OrderItemProductTests(TestCase):
    def test_name_and_price_are_filled_from_product(self):
        product = make_product(price=250000)
        order = make_stock_order(make_customer(), Order.Status.NEW, [(product, 2)])
        item = order.items.get()
        self.assertEqual(item.product_name, product.name)
        self.assertEqual(item.unit_price, Decimal("250000"))
        self.assertEqual(order.total_amount, Decimal("500000"))

    def test_custom_price_is_kept(self):
        product = make_product(price=250000)
        order = Order.objects.create(customer=make_customer())
        item = OrderItem.objects.create(order=order, product=product, quantity=1, unit_price=Decimal("200000"))
        self.assertEqual(item.unit_price, Decimal("200000"))


class StockSyncTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.product = make_product(stock=10)

    def test_new_order_does_not_touch_stock(self):
        make_stock_order(self.customer, Order.Status.NEW, [(self.product, 3)])
        self.assertEqual(stock_of(self.product), 10)

    def test_completed_order_deducts_stock(self):
        make_stock_order(self.customer, Order.Status.COMPLETED, [(self.product, 3)])
        self.assertEqual(stock_of(self.product), 7)

    def test_completing_later_deducts_once(self):
        order = make_stock_order(self.customer, Order.Status.PROCESSING, [(self.product, 3)])
        order.status = Order.Status.COMPLETED
        order.save()
        order.save()
        self.assertEqual(stock_of(self.product), 7)

    def test_cancelling_completed_order_restores_stock(self):
        order = make_stock_order(self.customer, Order.Status.COMPLETED, [(self.product, 3)])
        order.status = Order.Status.CANCELLED
        order.save()
        self.assertEqual(stock_of(self.product), 10)

    def test_editing_completed_order_applies_only_the_difference(self):
        order = make_stock_order(self.customer, Order.Status.COMPLETED, [(self.product, 3)])
        order = Order.objects.get(pk=order.pk)
        item = order.items.get()
        item.quantity = 5
        order.items = [item]
        order.save()
        self.assertEqual(stock_of(self.product), 5)

    def test_insufficient_stock_rolls_back_the_whole_save(self):
        with self.assertRaises(InsufficientStockError):
            make_stock_order(self.customer, Order.Status.COMPLETED, [(self.product, 11)])
        self.assertEqual(stock_of(self.product), 10)
        self.assertFalse(Order.objects.exists())

    def test_deleting_completed_order_or_customer_restores_stock(self):
        order = make_stock_order(self.customer, Order.Status.COMPLETED, [(self.product, 4)])
        order.delete()
        self.assertEqual(stock_of(self.product), 10)

        make_stock_order(self.customer, Order.Status.COMPLETED, [(self.product, 4)])
        self.customer.delete()
        self.assertEqual(stock_of(self.product), 10)

    def test_service_products_are_not_tracked(self):
        service = make_product(sku="DV-01", stock=0, track_stock=False)
        make_stock_order(self.customer, Order.Status.COMPLETED, [(service, 5)])
        self.assertEqual(stock_of(service), 0)

    def test_low_stock_detection(self):
        make_product(sku="SP-02", stock=2, min_stock=2)
        make_product(sku="DV-02", stock=0, min_stock=0, track_stock=False)
        self.assertEqual([p.sku for p in Product.low_stock()], ["SP-02"])


class AnalyticsTests(TestCase):
    def test_top_products_counts_completed_orders_only(self):
        customer = make_customer()
        a = make_product(sku="A", name="Máy A", stock=50)
        b = make_product(sku="B", name="Máy B", stock=50)
        make_stock_order(customer, Order.Status.COMPLETED, [(a, 2), (b, 5)])
        make_stock_order(customer, Order.Status.COMPLETED, [(a, 1)])
        make_stock_order(customer, Order.Status.CANCELLED, [(a, 20)])
        top = analytics.top_products()
        self.assertEqual([(p["sku"], p["value"]) for p in top], [("B", 5), ("A", 3)])
        self.assertEqual(top[0]["revenue"], 500000)

    def test_monthly_revenue_has_twelve_months_ending_this_month(self):
        make_stock_order(make_customer(), Order.Status.COMPLETED, [(make_product(stock=5), 2)])
        months = analytics.monthly_revenue()
        self.assertEqual(len(months), 12)
        self.assertEqual(months[-1]["value"], 200000)
        self.assertEqual(sum(m["value"] for m in months), 200000)

    def test_data_as_of_follows_old_data_but_not_recent_data(self):
        self.assertEqual(analytics.data_as_of().date(), timezone.localdate())  # CSDL trống -> hôm nay
        order = make_stock_order(make_customer(), Order.Status.COMPLETED, [(make_product(stock=5), 2)])
        self.assertEqual(analytics.data_as_of().date(), timezone.localdate())  # dữ liệu mới -> vẫn hôm nay
        old = timezone.localtime() - timedelta(days=400)
        Order.objects.filter(pk=order.pk).update(created_at=old)
        self.assertEqual(analytics.data_as_of(), old)  # chỉ có dữ liệu cũ -> neo theo dữ liệu mới nhất
        months = analytics.monthly_revenue(as_of=old)
        self.assertEqual(months[-1], {"label": f"T{old.month}/{old.year}", "value": 200000})


class DashboardAndAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pass")
        self.client.force_login(self.user)

    def test_dashboard_renders_charts_and_low_stock(self):
        product = make_product(sku="SP-LOW", name="Giấy in", stock=6, min_stock=5)
        make_stock_order(make_customer(), Order.Status.COMPLETED, [(product, 2)])
        response = self.client.get(reverse("crm:dashboard"))
        self.assertContains(response, 'id="dashboard-charts"')
        self.assertContains(response, "SP-LOW")
        charts = response.context["charts"]
        json.dumps(charts)  # phải JSON được để đưa vào json_script
        self.assertEqual(set(charts), {"revenue", "status", "customers", "products"})
        self.assertEqual(charts["products"][0]["value"], 2)

    def _post_order(self, product, quantity, status):
        return self.client.post(reverse("wagtailsnippets_crm_order:add"), {
            "customer": make_customer().pk,
            "status": status,
            "note": "",
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1", "items-MAX_NUM_FORMS": "1000",
            "items-0-product": product.pk, "items-0-product_name": "",
            "items-0-quantity": str(quantity), "items-0-unit_price": "",
            "items-0-ORDER": "1", "items-0-id": "", "items-0-DELETE": "",
        })

    def test_admin_blocks_completing_order_without_enough_stock(self):
        product = make_product(stock=1)
        response = self._post_order(product, 3, Order.Status.COMPLETED)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Không đủ hàng trong kho")
        self.assertFalse(Order.objects.exists())
        self.assertEqual(stock_of(product), 1)

    def test_admin_completes_order_and_deducts_stock(self):
        product = make_product(stock=5, price=300000)
        response = self._post_order(product, 3, Order.Status.COMPLETED)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(stock_of(product), 2)
        self.assertEqual(Order.objects.get().total_amount, Decimal("900000"))
