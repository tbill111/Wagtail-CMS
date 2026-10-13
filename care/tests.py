from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from care.models import Campaign, CampaignMember, SupportTicket
from crm.models import Customer, Order
from crm.tests.factories import make_customer, make_order


def make_ticket(customer=None, **kwargs):
    defaults = {"subject": "Máy in lỗi", "description": "Không in được hoá đơn."}
    defaults.update(kwargs)
    return SupportTicket.objects.create(customer=customer or make_customer(), **defaults)


class SupportTicketTests(TestCase):
    def test_code_increases_per_day(self):
        customer = make_customer()
        first, second = make_ticket(customer), make_ticket(customer)
        today = timezone.localdate()
        self.assertEqual(first.code, f"HT-{today:%Y%m%d}-0001")
        self.assertEqual(second.code, f"HT-{today:%Y%m%d}-0002")

    def test_due_date_follows_priority(self):
        before = timezone.now()
        high = make_ticket(priority=Customer.Priority.HIGH)
        low = make_ticket(high.customer, priority=Customer.Priority.LOW)
        self.assertAlmostEqual(high.due_at, before + timedelta(hours=4), delta=timedelta(minutes=1))
        self.assertAlmostEqual(low.due_at, before + timedelta(hours=72), delta=timedelta(minutes=1))

    def test_manual_due_date_is_kept(self):
        due = timezone.now() + timedelta(days=10)
        self.assertEqual(make_ticket(due_at=due).due_at, due)

    def test_resolving_sets_time_and_reopening_clears_it(self):
        ticket = make_ticket()
        self.assertIsNone(ticket.resolved_at)
        ticket.status, ticket.resolution = SupportTicket.Status.RESOLVED, "Đã cài lại driver."
        ticket.save()
        resolved_at = ticket.resolved_at
        self.assertIsNotNone(resolved_at)
        ticket.status = SupportTicket.Status.CLOSED
        ticket.save()
        self.assertEqual(ticket.resolved_at, resolved_at)  # đóng phiếu không đổi thời điểm giải quyết
        ticket.status = SupportTicket.Status.IN_PROGRESS
        ticket.save()
        self.assertIsNone(ticket.resolved_at)

    def test_overdue(self):
        ticket = make_ticket(due_at=timezone.now() - timedelta(hours=1))
        self.assertTrue(ticket.is_overdue)
        self.assertEqual(list(SupportTicket.open_overdue()), [ticket])
        on_time = make_ticket(ticket.customer, due_at=timezone.now() + timedelta(hours=1))
        self.assertFalse(on_time.is_overdue)
        # Xử lý xong trễ hạn vẫn tính là quá hạn, nhưng không còn nằm trong danh sách cần xử lý
        ticket.status, ticket.resolution = SupportTicket.Status.RESOLVED, "Xong."
        ticket.save()
        self.assertTrue(ticket.is_overdue)
        self.assertFalse(SupportTicket.open_overdue().exists())

    def test_done_requires_resolution(self):
        ticket = make_ticket()
        ticket.status = SupportTicket.Status.RESOLVED
        with self.assertRaises(ValidationError) as ctx:
            ticket.full_clean()
        self.assertIn("resolution", ctx.exception.message_dict)

    def test_satisfaction_only_when_done(self):
        ticket = make_ticket()
        ticket.satisfaction = 5
        with self.assertRaises(ValidationError) as ctx:
            ticket.full_clean()
        self.assertIn("satisfaction", ctx.exception.message_dict)

    def test_order_must_belong_to_customer(self):
        other = make_customer(email="khac@example.com")
        ticket = make_ticket()
        ticket.order = make_order(other)
        with self.assertRaises(ValidationError) as ctx:
            ticket.full_clean()
        self.assertIn("order", ctx.exception.message_dict)


class CampaignTests(TestCase):
    def setUp(self):
        self.lead_fb = make_customer(email="a@example.com", status="lead", source="facebook")
        self.lead_web = make_customer(email="b@example.com", status="lead", source="website")
        self.buyer = make_customer(email="c@example.com", status="customer", source="facebook")

    def members(self, campaign):
        return set(campaign.members.values_list("customer_id", flat=True))

    def test_draft_lists_customers_matching_target(self):
        campaign = Campaign.objects.create(name="Chào lead Facebook", target_status="lead", target_source="facebook")
        self.assertEqual(self.members(campaign), {self.lead_fb.pk})
        campaign.target_source = ""
        campaign.save()
        self.assertEqual(self.members(campaign), {self.lead_fb.pk, self.lead_web.pk})
        campaign.target_status = "customer"
        campaign.save()
        self.assertEqual(self.members(campaign), {self.buyer.pk})

    def test_empty_target_means_everyone(self):
        self.assertEqual(Campaign.objects.create(name="Tất cả").member_count, 3)

    def test_contacted_member_survives_target_change(self):
        campaign = Campaign.objects.create(name="Lead", target_status="lead")
        campaign.members.filter(customer=self.lead_fb).update(response=CampaignMember.Response.SENT)
        campaign.target_status = "customer"
        campaign.save()
        self.assertEqual(self.members(campaign), {self.lead_fb.pk, self.buyer.pk})

    def test_running_campaign_keeps_its_list(self):
        campaign = Campaign.objects.create(name="Lead", target_status="lead")
        campaign.status = Campaign.Status.RUNNING
        campaign.target_status = "customer"
        campaign.save()
        make_customer(email="d@example.com", status="customer")
        campaign.save()
        self.assertEqual(self.members(campaign), {self.lead_fb.pk, self.lead_web.pk})

    def test_rates(self):
        campaign = Campaign.objects.create(name="Tất cả")
        self.assertEqual(campaign.response_rate, "–")
        responses = dict(zip([self.lead_fb, self.lead_web, self.buyer], ["sent", "responded", "converted"]))
        for customer, response in responses.items():
            member = campaign.members.get(customer=customer)
            member.response = response
            member.save()
            self.assertIsNotNone(member.contacted_at)
        make_customer(email="d@example.com")
        campaign.save()  # khách mới vào danh sách ở trạng thái Chưa liên hệ – không tính vào mẫu số
        self.assertEqual(campaign.member_count, 4)
        self.assertEqual(campaign.contacted_count, 3)
        self.assertEqual(campaign.response_rate, "67%")
        self.assertEqual(campaign.conversion_rate, "33%")

    def test_revenue_counts_completed_orders_of_converted_members_in_period(self):
        today = timezone.localdate()
        campaign = Campaign.objects.create(name="Tất cả", start_date=today - timedelta(days=5))
        campaign.members.filter(customer=self.buyer).update(response=CampaignMember.Response.CONVERTED)
        make_order(self.buyer)  # 2 × 100.000, Hoàn thành, trong thời gian chiến dịch
        make_order(self.buyer, status=Order.Status.NEW)  # chưa hoàn thành
        make_order(self.lead_fb)  # khách chưa chuyển đổi
        old = make_order(self.buyer)
        Order.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))  # trước chiến dịch
        self.assertEqual(campaign.revenue, 200000)

    def test_customer_appears_once_per_campaign(self):
        campaign = Campaign.objects.create(name="Tất cả")
        with self.assertRaises(IntegrityError), transaction.atomic():
            CampaignMember.objects.create(campaign=campaign, customer=self.buyer)

    def test_end_date_must_follow_start_date(self):
        today = timezone.localdate()
        campaign = Campaign(name="Sai ngày", start_date=today, end_date=today - timedelta(days=1))
        with self.assertRaises(ValidationError):
            campaign.full_clean()


class AdminTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin", "admin@example.com", "pass"))
        self.customer = make_customer()

    def test_listings_and_forms_open(self):
        ticket = make_ticket(self.customer)
        campaign = Campaign.objects.create(name="Tất cả")
        member = campaign.members.get()
        for model, pk in (("supportticket", ticket.pk), ("campaign", campaign.pk), ("campaignmember", member.pk)):
            for url in (
                reverse(f"wagtailsnippets_care_{model}:list"),
                reverse(f"wagtailsnippets_care_{model}:add"),
                reverse(f"wagtailsnippets_care_{model}:edit", args=[pk]),
            ):
                self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_ticket_cannot_be_resolved_without_resolution_in_admin(self):
        response = self.client.post(reverse("wagtailsnippets_care_supportticket:add"), {
            "customer": self.customer.pk, "subject": "Máy in lỗi", "description": "Không in được.",
            "category": "technical", "channel": "phone", "status": "resolved", "priority": "high",
            "notes-TOTAL_FORMS": 0, "notes-INITIAL_FORMS": 0, "notes-MIN_NUM_FORMS": 0, "notes-MAX_NUM_FORMS": 1000,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nhập kết quả xử lý trước khi chuyển sang")
        self.assertFalse(SupportTicket.objects.exists())


class SeedCareTests(TestCase):
    def seed(self, **options):
        call_command("seed_care", tickets=12, stdout=StringIO(), **options)

    def test_needs_customers(self):
        with self.assertRaises(CommandError):
            self.seed()

    def test_creates_tickets_and_campaigns_and_can_reset(self):
        for index, (status, source) in enumerate([("lead", "facebook"), ("customer", "website"), ("churned", "other")]):
            make_customer(email=f"kh{index}@example.com", status=status, source=source)
        self.seed()
        self.assertEqual(SupportTicket.objects.count(), 12)
        self.assertEqual(Campaign.objects.count(), 3)
        self.assertTrue(CampaignMember.objects.exists())
        for ticket in SupportTicket.objects.filter(status__in=SupportTicket.DONE_STATUSES):
            self.assertGreater(ticket.resolved_at, ticket.created_at)
        with self.assertRaises(CommandError):
            self.seed()
        self.seed(reset=True)
        self.assertEqual(SupportTicket.objects.count(), 12)
        self.assertEqual(Campaign.objects.count(), 3)
