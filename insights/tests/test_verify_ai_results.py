from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from crm.models import Customer
from insights.models import ChurnScore, ModelRun, RevenueForecast


class VerifyAIResultsTest(TestCase):
    def setUp(self):
        now = timezone.now()

        self.customer = Customer.objects.create(
            name='Khách hàng test',
            email='test.customer@example.com',
        )

        self.run_rev = ModelRun.objects.create(
            batch='batch-01',
            module='forecast',
            method='baseline',
            is_selected=True,
            status='success',
            started_at=now,
            metrics={'mae': 10},
        )
        RevenueForecast.objects.create(
            run=self.run_rev,
            month=now.date() - timedelta(days=30),
            kind='history',
            actual=1000,
            forecast=1000,
            lower=900,
            upper=1100,
        )

        self.run_churn = ModelRun.objects.create(
            batch='batch-02',
            module='churn',
            method='xgboost',
            is_selected=True,
            status='success',
            started_at=now,
        )
        ChurnScore.objects.create(
            run=self.run_churn,
            customer=self.customer,
            probability=0.5,
            risk_band='medium',
        )

    def test_command_success(self):
        out = StringIO()
        call_command('verify_ai_results', stdout=out)
        self.assertIn('Hoàn tất! Tất cả các mục đều KHỚP', out.getvalue())

    def test_command_failure_multiple_selected(self):
        ModelRun.objects.create(
            batch='batch-03',
            module='forecast',
            method='baseline-2',
            is_selected=True,
            status='success',
            started_at=timezone.now(),
            metrics={'mae': 15},
        )
        with self.assertRaises(CommandError) as context:
            call_command('verify_ai_results')
        self.assertTrue('Phát hiện dữ liệu LỆCH' in str(context.exception))
