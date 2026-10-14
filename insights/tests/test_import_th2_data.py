import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone

from crm.analytics import COMPLETED_ITEMS, LINE_TOTAL
from crm.models import Customer, InteractionLog, Order, OrderItem, Product
from insights.models import SentimentLabel

RETAIL = """Invoice,StockCode,Description,Quantity,InvoiceDate,Price,Customer ID,Country
100,85048,GLASS BALL,2,2010-01-05 10:00:00,1.5,111,United Kingdom
100,85048,GLASS BALL,1,2010-01-05 10:00:00,1.5,111,United Kingdom
100,POST,POSTAGE,1,2010-01-05 10:00:00,18,111,United Kingdom
101,22423,REGENCY CAKESTAND,1,2011-06-01 09:00:00,10,222,France
102,22423,REGENCY CAKESTAND,1,2011-06-01 11:00:00,0,222,France
C103,22423,REGENCY CAKESTAND,-1,2011-06-02 09:00:00,10,222,France
104,85048,GLASS BALL,5,2011-06-03 09:00:00,1.5,,United Kingdom
105,85048,GLASS BALL,3,2011-12-09 09:00:00,1.5,333,Germany
"""
REVIEWS = """comment,label
Máy tốt pin trâu,5
Bình thường,3
Pin hao quá thất vọng,1
Giao hàng nhanh,4
"""


class ImportTh2DataTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "retail.csv").write_text(RETAIL, encoding="utf-8")
        (self.tmp / "reviews.csv").write_text(REVIEWS, encoding="utf-8")

    def run_import(self, **options):
        defaults = {"customers": 3, "reviews_count": 4, "allow_any_db": True}
        call_command("import_th2_data", retail=str(self.tmp / "retail.csv"), reviews=[str(self.tmp / "reviews.csv")],
                     stdout=StringIO(), **{**defaults, **options})

    def test_imports_customers_orders_with_conventions(self):
        self.run_import()
        self.assertEqual(Customer.objects.count(), 3)
        # bỏ mã POST, dòng giá 0 và dòng không có mã khách; gộp 2 dòng cùng mã hàng cùng giá
        self.assertEqual(Product.objects.count(), 2)
        self.assertFalse(Product.objects.filter(track_stock=True).exists())
        order = Order.objects.get(note__contains="hoá đơn 100")
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(list(order.items.values_list("quantity", "unit_price")), [(3, 49_500)])
        self.assertEqual(timezone.localtime(order.created_at).year, 2024)  # dời +14 năm
        self.assertTrue(order.code.startswith("DH-20240105-"))
        self.assertEqual(Order.objects.get(note__contains="hoá đơn C103").status, Order.Status.CANCELLED)
        revenue = OrderItem.objects.filter(COMPLETED_ITEMS).aggregate(t=Sum(LINE_TOTAL))["t"]
        self.assertEqual(revenue, 3 * 49_500 + 330_000 + 3 * 49_500)

    def test_status_churned_after_180_days_without_purchase(self):
        self.run_import()
        self.assertEqual(Customer.objects.get(email__startswith="uk111@").status, Customer.Status.CHURNED)
        self.assertEqual(Customer.objects.get(email__startswith="uk333@").status, Customer.Status.CUSTOMER)

    def test_reviews_become_interactions_with_true_labels(self):
        self.run_import()
        self.assertEqual(InteractionLog.objects.count(), 4)
        labels = dict(SentimentLabel.objects.values_list("interaction__customer_message", "label"))
        self.assertEqual(labels["Máy tốt pin trâu"], "positive")
        self.assertEqual(labels["Bình thường"], "neutral")
        self.assertEqual(labels["Pin hao quá thất vọng"], "negative")

    def test_same_input_gives_same_result_and_requires_clear(self):
        self.run_import()
        first = sorted(Order.objects.values_list("code", "status"))
        with self.assertRaises(CommandError):
            self.run_import()
        self.run_import(clear=True)
        self.assertEqual(sorted(Order.objects.values_list("code", "status")), first)

    def test_refuses_non_th2_database_without_flag(self):
        # cố định tên CSDL: khi chạy test với DB_NAME=smartcrm_th2 thì CSDL test cũng có đuôi _th2
        with mock.patch.dict(connection.settings_dict, {"NAME": "test_smartcrm"}), \
                self.assertRaisesMessage(CommandError, "smartcrm_th2"):
            self.run_import(allow_any_db=False)
        with mock.patch.dict(connection.settings_dict, {"NAME": "test_smartcrm_th2"}):
            self.run_import(allow_any_db=False)
        self.assertEqual(Customer.objects.count(), 3)
