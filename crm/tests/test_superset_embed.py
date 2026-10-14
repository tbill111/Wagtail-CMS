from unittest import mock

import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from crm.services import superset

UUID = "dcf734a5-0000-4000-8000-61c5c304c813"


def fake_superset(request):
    """Giả lập các API Superset mà ``embed_credentials`` gọi."""
    path = request.url.path
    if path == "/api/v1/security/login":
        return httpx.Response(200, json={"access_token": "jwt"})
    if path in ("/api/v1/dashboard/smartcrm-th1/embedded", "/api/v1/dashboard/smartcrm-ai-insights/embedded"):
        return httpx.Response(200, json={"result": {"uuid": UUID}})
    if path == "/api/v1/security/csrf_token/":
        return httpx.Response(200, json={"result": "csrf"})
    if path == "/api/v1/security/guest_token/":
        return httpx.Response(200, json={"token": "guest-token"})
    return httpx.Response(500)


def patch_transport(handler):
    real_client = httpx.Client
    return mock.patch.object(
        superset.httpx, "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )


@override_settings(SUPERSET_URL="http://superset.test", SUPERSET_ADMIN_USER="admin", SUPERSET_ADMIN_PASSWORD="x")
class EmbedCredentialsTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("nhanvien", password="matkhau123", is_staff=True)

    def test_returns_uuid_and_guest_token_scoped_to_dashboard(self):
        seen = {}

        def handler(request):
            if request.url.path.endswith("/guest_token/"):
                seen["body"] = request.content.decode()
                seen["auth"] = request.headers["Authorization"]
            return fake_superset(request)

        with patch_transport(handler):
            result = superset.embed_credentials(self.staff, "smartcrm-th1")
        self.assertEqual(result, {"uuid": UUID, "token": "guest-token"})
        self.assertEqual(seen["auth"], "Bearer jwt")
        self.assertIn(f'"resources":[{{"type":"dashboard","id":"{UUID}"}}]', seen["body"].replace(" ", ""))
        self.assertIn('"username":"nhanvien"', seen["body"].replace(" ", ""))

    def test_dashboard_not_embedded_gives_bootstrap_hint(self):
        def handler(request):
            if request.url.path.endswith("/embedded"):
                return httpx.Response(404, json={"message": "Not found"})
            return fake_superset(request)

        with patch_transport(handler), self.assertRaisesMessage(superset.SupersetError, "bootstrap_dashboard.py"):
            superset.embed_credentials(self.staff, "smartcrm-th1")

    def test_superset_down_gives_friendly_error(self):
        def handler(request):
            raise httpx.ConnectError("refused")

        with patch_transport(handler), self.assertRaisesMessage(superset.SupersetError, "Không kết nối được Superset"):
            superset.embed_credentials(self.staff, "smartcrm-th1")

    @override_settings(SUPERSET_ADMIN_PASSWORD="")
    def test_missing_password_does_not_call_superset(self):
        with self.assertRaisesMessage(superset.SupersetError, "SUPERSET_ADMIN_PASSWORD"):
            superset.embed_credentials(self.staff, "smartcrm-th1")


DASHBOARDS = [("ai", "AI Insights", "smartcrm-ai-insights"), ("kinh-doanh", "Phân tích kinh doanh", "smartcrm-th1")]


@override_settings(SUPERSET_URL="http://superset.test", SUPERSET_DASHBOARDS=DASHBOARDS)
class AnalyticsViewTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("nhanvien", password="matkhau123", is_staff=True)
        self.page_url = reverse("crm:analytics_page")
        self.token_url = reverse("crm:api_superset_guest_token")

    def test_anonymous_is_blocked(self):
        self.assertEqual(self.client.get(self.page_url).status_code, 302)
        self.assertEqual(self.client.post(self.token_url).status_code, 401)

    def test_non_staff_cannot_get_token(self):
        self.client.force_login(get_user_model().objects.create_user("khach", password="matkhau123"))
        self.assertEqual(self.client.post(self.token_url).status_code, 403)

    def test_page_renders_and_sends_referrer_to_superset(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.page_url)
        self.assertContains(response, "Phân tích | SmartCRM")
        self.assertContains(response, 'data-superset-url="http://superset.test"')
        self.assertContains(response, "http://superset.test/superset/dashboard/smartcrm-ai-insights/")
        self.assertContains(response, 'data-dashboard="ai"')
        self.assertContains(response, 'href="?tab=kinh-doanh"')
        second = self.client.get(self.page_url, {"tab": "kinh-doanh"})
        self.assertContains(second, "http://superset.test/superset/dashboard/smartcrm-th1/")
        unknown = self.client.get(self.page_url, {"tab": "khong-co"})
        self.assertContains(unknown, 'data-dashboard="ai"')
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_token_api_returns_credentials(self):
        self.client.force_login(self.staff)
        with mock.patch.object(superset, "embed_credentials", return_value={"uuid": UUID, "token": "t"}) as fake:
            response = self.client.post(self.token_url, {"dashboard": "kinh-doanh"},
                                        content_type="application/json")
        self.assertEqual(response.json(), {"ok": True, "uuid": UUID, "token": "t"})
        fake.assert_called_once_with(self.staff, "smartcrm-th1")

    def test_dashboard_setting_parser_ignores_malformed_items(self):
        from smartcrm.settings.base import parse_dashboards

        self.assertEqual(parse_dashboards("ai:AI Insights:smartcrm-ai, sai-dinh-dang, x::y,:a:b"),
                         [("ai", "AI Insights", "smartcrm-ai")])
        self.assertEqual(parse_dashboards(""), [])

    def test_token_api_defaults_to_first_tab_and_rejects_unknown_dashboard(self):
        self.client.force_login(self.staff)
        with mock.patch.object(superset, "embed_credentials", return_value={"uuid": UUID, "token": "t"}) as fake:
            self.client.post(self.token_url)
            fake.assert_called_once_with(self.staff, "smartcrm-ai-insights")
            response = self.client.post(self.token_url, {"dashboard": "khong-co"}, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_token_api_rejects_get_and_reports_superset_error(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.token_url).status_code, 405)
        with mock.patch.object(superset, "embed_credentials", side_effect=superset.SupersetError("Superset tắt")):
            response = self.client.post(self.token_url)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"ok": False, "error": "Superset tắt"})
