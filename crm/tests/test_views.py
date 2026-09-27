import json
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from crm.models import AIReport, Customer, InteractionLog
from crm.services.ai_service import AIServiceError, GeminiCRMService

from .factories import make_customer, make_order


class BaseViewTest(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            "nhanvien", "nv@example.com", "matkhau123", is_staff=True
        )
        self.customer = make_customer(name="Hoàng Minh Đức")
        self.client.force_login(self.staff)

    def post_json(self, url, data):
        return self.client.post(url, json.dumps(data), content_type="application/json")

    def suggest_url(self, pk=None):
        return reverse("crm:api_suggest_reply", args=[pk or self.customer.pk])

    def save_url(self, pk=None):
        return reverse("crm:api_save_interaction", args=[pk or self.customer.pk])


class AccessTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        for name, args in [("crm:dashboard", []), ("crm:customer_list", []), ("crm:customer_detail", [1])]:
            response = self.client.get(reverse(name, args=args))
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/login/", response["Location"])

    def test_non_staff_user_cannot_access(self):
        user = get_user_model().objects.create_user("khach", password="matkhau123")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("crm:dashboard")).status_code, 302)
        response = self.client.post(reverse("crm:api_suggest_reply", args=[1]), {"message": "a"})
        self.assertEqual(response.status_code, 403)

    def test_anonymous_api_returns_401_json(self):
        response = self.client.post(reverse("crm:api_suggest_reply", args=[1]), {"message": "a"})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["ok"])


class PageTests(BaseViewTest):
    def test_dashboard_list_and_detail_render(self):
        make_order(self.customer)
        self.assertContains(self.client.get(reverse("crm:dashboard")), "Tổng quan | SmartCRM")
        self.assertContains(self.client.get(reverse("crm:customer_list")), "Hoàng Minh Đức")
        detail = self.client.get(reverse("crm:customer_detail", args=[self.customer.pk]))
        self.assertContains(detail, "✨ Gợi ý phản hồi AI")
        self.assertContains(detail, 'id="ai-extra-panels"')
        self.assertContains(detail, "Chưa có tương tác nào")

    def test_customer_list_search_filter_and_pagination(self):
        for i in range(12):
            make_customer(name=f"Khách {i:02d}", email=f"k{i}@example.com", status="caring")
        response = self.client.get(reverse("crm:customer_list"), {"status": "caring"})
        self.assertEqual(response.context["page_obj"].paginator.count, 12)
        self.assertEqual(len(response.context["customers"]), 10)
        response = self.client.get(reverse("crm:customer_list"), {"q": "Minh Đức"})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

    def test_detail_404_for_unknown_customer(self):
        self.assertEqual(self.client.get(reverse("crm:customer_detail", args=[9999])).status_code, 404)


class SuggestReplyApiTests(BaseViewTest):
    def test_returns_200_with_reply(self):
        with mock.patch.object(GeminiCRMService, "suggest_reply", return_value="Kính gửi anh Đức ...") as fake:
            response = self.post_json(self.suggest_url(), {"message": "Khi nào giao hàng?", "tone": "thân thiện"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["reply"], "Kính gửi anh Đức ...")
        self.assertIn("mock", data)
        fake.assert_called_once_with(self.customer, "Khi nào giao hàng?", tone="thân thiện")

    @override_settings(GEMINI_API_KEY="", AI_MOCK=True)
    def test_mock_mode_end_to_end(self):
        response = self.post_json(self.suggest_url(), {"message": "Xin chào"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["mock"])
        self.assertEqual(response.json()["provider"], "AI Gemini")
        self.assertIn("Hoàng Minh Đức", response.json()["reply"])

    def test_returns_400_for_invalid_input(self):
        self.assertEqual(self.post_json(self.suggest_url(), {"message": "   "}).status_code, 400)
        self.assertEqual(self.post_json(self.suggest_url(), {"message": "a" * 2001}).status_code, 400)
        self.assertEqual(self.post_json(self.suggest_url(), {"message": "ok", "tone": "hài hước"}).status_code, 400)
        bad_json = self.client.post(self.suggest_url(), "{khong-phai-json", content_type="application/json")
        self.assertEqual(bad_json.status_code, 400)

    def test_returns_404_for_unknown_customer(self):
        self.assertEqual(self.post_json(self.suggest_url(pk=9999), {"message": "Xin chào"}).status_code, 404)

    def test_returns_503_when_ai_fails(self):
        with mock.patch.object(GeminiCRMService, "suggest_reply", side_effect=AIServiceError("AI lỗi")):
            response = self.post_json(self.suggest_url(), {"message": "Xin chào"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"ok": False, "error": "AI lỗi"})

    def test_only_post_allowed(self):
        self.assertEqual(self.client.get(self.suggest_url()).status_code, 405)


class SaveInteractionApiTests(BaseViewTest):
    def test_creates_interaction_and_returns_html(self):
        response = self.post_json(self.save_url(), {
            "message": "Khi nào giao hàng?",
            "ai_suggested_reply": "Bản AI gốc",
            "final_reply": "Bản đã chỉnh sửa",
            "channel": "email",
        })
        self.assertEqual(response.status_code, 201)
        log = InteractionLog.objects.get()
        self.assertEqual(log.customer, self.customer)
        self.assertEqual(log.staff, self.staff)
        self.assertEqual(log.ai_suggested_reply, "Bản AI gốc")
        self.assertEqual(log.final_reply, "Bản đã chỉnh sửa")
        self.assertTrue(log.is_ai_generated)
        self.assertTrue(response.json()["ok"])
        self.assertIn("Bản đã chỉnh sửa", response.json()["interaction_html"])

    def test_validation_errors(self):
        self.assertEqual(self.post_json(self.save_url(), {"message": "", "final_reply": "x"}).status_code, 400)
        self.assertEqual(self.post_json(self.save_url(), {"message": "x", "final_reply": ""}).status_code, 400)
        self.assertEqual(
            self.post_json(self.save_url(), {"message": "x", "final_reply": "y", "channel": "fax"}).status_code, 400
        )
        self.assertEqual(self.post_json(self.save_url(pk=9999), {"message": "x", "final_reply": "y"}).status_code, 404)
        self.assertFalse(InteractionLog.objects.exists())



NEW_AI_APIS = [
    ("crm:api_analyze_customer", True),
    ("crm:api_apply_status", True),
    ("crm:api_generate_report", False),
]


def api_url(name, needs_pk, pk=1):
    return reverse(name, args=[pk] if needs_pk else [])


class ClassifyApiTests(BaseViewTest):
    def analyze_url(self, pk=None):
        return reverse("crm:api_analyze_customer", args=[pk or self.customer.pk])

    def apply_url(self, pk=None):
        return reverse("crm:api_apply_status", args=[pk or self.customer.pk])

    @override_settings(AI_MOCK=True)
    def test_analyze_returns_full_data_with_provider(self):
        make_order(self.customer, items=[("Gói phần mềm", 1, 2000000)])
        with mock.patch("httpx.post") as post:
            response = self.post_json(self.analyze_url(), {})
        post.assert_not_called()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["mock"])
        self.assertEqual(payload["provider"], "AI Gemini")
        data = payload["data"]
        for key in ["sentiment", "sentiment_display", "priority", "priority_display", "suggested_status",
                    "suggested_status_display", "summary", "next_actions", "analyzed_at", "status", "can_apply"]:
            self.assertIn(key, data)
        self.customer.refresh_from_db()
        self.assertEqual(data["can_apply"], self.customer.ai_suggested_status != self.customer.status)
        # Giờ hiển thị theo múi giờ Việt Nam, khớp với template (|date:"d/m/Y H:i")
        local = timezone.localtime(self.customer.ai_analyzed_at).strftime("%d/%m/%Y %H:%M")
        self.assertEqual(data["analyzed_at"], local)

    def test_analyze_ai_error_returns_503(self):
        with mock.patch.object(GeminiCRMService, "analyze_customer", side_effect=AIServiceError("Gemini quá tải")):
            response = self.post_json(self.analyze_url(), {})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "Gemini quá tải")

    def test_analyze_404_and_405(self):
        with mock.patch.object(GeminiCRMService, "analyze_customer") as fake:
            self.assertEqual(self.post_json(self.analyze_url(pk=9999), {}).status_code, 404)
            self.assertEqual(self.client.get(self.analyze_url()).status_code, 405)
        fake.assert_not_called()

    def test_apply_status_changes_status_and_returns_badge(self):
        self.customer.ai_suggested_status = "caring"
        self.customer.save()
        response = self.post_json(self.apply_url(), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"ok": True, "status": "caring", "status_display": "Đang chăm sóc", "badge_class": "text-bg-warning"},
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, "caring")

    def test_apply_status_400_without_suggestion_or_same_status(self):
        self.assertEqual(self.post_json(self.apply_url(), {}).status_code, 400)
        self.customer.ai_suggested_status = self.customer.status
        self.customer.save()
        self.assertEqual(self.post_json(self.apply_url(), {}).status_code, 400)

    def test_detail_hides_apply_button_when_suggestion_equals_status(self):
        self.customer.ai_analyzed_at = timezone.now()
        self.customer.ai_suggested_status = self.customer.status
        self.customer.save()
        response = self.client.get(reverse("crm:customer_detail", args=[self.customer.pk]))
        self.assertContains(response, 'id="customer-status-badge"')
        self.assertContains(response, "✨ Phân tích lại")
        self.assertRegex(response.content.decode(), r'd-none" id="classify-status-suggest"')


class NewApiPermissionTests(TestCase):
    def test_anonymous_gets_401_json_and_non_staff_gets_403(self):
        for name, needs_pk in NEW_AI_APIS:
            response = self.client.post(api_url(name, needs_pk), "{}", content_type="application/json")
            self.assertEqual(response.status_code, 401, name)
            self.assertFalse(response.json()["ok"])
        self.client.force_login(get_user_model().objects.create_user("khach", password="matkhau123"))
        for name, needs_pk in NEW_AI_APIS:
            response = self.client.post(api_url(name, needs_pk), "{}", content_type="application/json")
            self.assertEqual(response.status_code, 403, name)


class ReportTests(BaseViewTest):
    url = "/crm/api/reports/generate/"

    @override_settings(AI_MOCK=True)
    def test_generate_returns_insight_and_saves_ai_report(self):
        make_order(self.customer, items=[("Gói phần mềm", 1, 2000000)])
        response = self.post_json(self.url, {})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in ["stats", "insight", "generated_at", "mock", "provider"]:
            self.assertIn(key, payload)
        self.assertEqual(payload["stats"]["revenue"], 2000000)
        report = AIReport.objects.get()
        self.assertEqual(report.content, payload["insight"])
        self.assertEqual(report.stats["revenue"], 2000000)
        self.assertEqual((report.provider, report.is_mock, report.created_by), ("AI Gemini", True, self.staff))

    def test_generate_ai_error_returns_503_and_saves_nothing(self):
        with mock.patch.object(GeminiCRMService, "generate_report", side_effect=AIServiceError("Hết quota")):
            response = self.post_json(self.url, {})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(AIReport.objects.exists())

    def test_empty_database_returns_400_without_calling_ai(self):
        self.customer.delete()
        with mock.patch.object(GeminiCRMService, "generate_report") as fake:
            response = self.post_json(self.url, {})
            page = self.client.get(reverse("crm:report_page"))
        self.assertEqual(response.status_code, 400)
        fake.assert_not_called()
        self.assertNotContains(page, 'id="report-btn"')

    def test_report_page_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("crm:report_page"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_navbar_has_report_link_on_every_crm_page(self):
        pages = [
            reverse("crm:dashboard"),
            reverse("crm:customer_list"),
            reverse("crm:customer_detail", args=[self.customer.pk]),
            reverse("crm:report_page"),
        ]
        link = f'href="{reverse("crm:report_page")}">Báo cáo AI</a>'
        for url in pages:
            self.assertContains(self.client.get(url), link, msg_prefix=url)
        self.assertContains(self.client.get(reverse("crm:report_page")), "<title>Báo cáo AI | SmartCRM</title>")


class AIReportAdminTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser("admin", "admin@example.com", "matkhau123")
        self.client.force_login(admin)
        self.report = AIReport.objects.create(content="Nhận định", stats={"revenue": 1}, provider="AI Gemini")

    def test_ai_report_is_view_only_in_admin(self):
        self.assertEqual(self.client.get("/admin/snippets/crm/aireport/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/snippets/crm/aireport/inspect/{self.report.pk}/").status_code, 200)
        self.client.post("/admin/snippets/crm/aireport/add/", {})
        self.client.post(f"/admin/snippets/crm/aireport/delete/{self.report.pk}/")
        self.assertEqual(list(AIReport.objects.values_list("content", flat=True)), ["Nhận định"])
        for url in ["add/", f"edit/{self.report.pk}/", f"delete/{self.report.pk}/"]:
            self.assertNotEqual(self.client.get(f"/admin/snippets/crm/aireport/{url}").status_code, 200, url)


class SeedDemoAnalyzeTests(TestCase):
    @override_settings(AI_MOCK=False, GEMINI_API_KEY="test-key-khong-that", FALLBACK_AI_API_KEY="")
    def test_analyze_option_uses_mock_and_can_run_twice(self):
        client = mock.MagicMock()
        with mock.patch.object(GeminiCRMService, "client", new_callable=mock.PropertyMock, return_value=client), \
                mock.patch("httpx.post") as post:
            call_command("seed_demo", "--analyze", stdout=StringIO())
            call_command("seed_demo", "--analyze", stdout=StringIO())
        client.models.generate_content.assert_not_called()
        post.assert_not_called()
        analyzed = Customer.objects.exclude(ai_analyzed_at=None)
        self.assertEqual(analyzed.count(), Customer.objects.count())
        self.assertTrue(all(c.ai_provider.endswith("(chế độ mô phỏng)") for c in analyzed))
