import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from crm.models import InteractionLog
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
