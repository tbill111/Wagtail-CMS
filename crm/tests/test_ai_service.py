from unittest import mock

import httpx

from django.test import TestCase, override_settings

from crm.models import InteractionLog, Order
from crm.services.ai_service import AIServiceError, GeminiCRMService, get_ai_service

from .factories import make_customer, make_order

LIVE = {
    "GEMINI_API_KEY": "test-key-khong-that",
    "AI_MOCK": False,
    "GEMINI_MODEL": "gemini-3.8-flash",
    "FALLBACK_AI_API_KEY": "",  # không phụ thuộc cấu hình .env của máy chạy test
}


def fake_client(text="Kính gửi anh Test, ..."):
    client = mock.MagicMock()
    client.models.generate_content.return_value = mock.MagicMock(text=text)
    return client


def patch_client(client):
    return mock.patch.object(GeminiCRMService, "client", new_callable=mock.PropertyMock, return_value=client)


class BuildContextTests(TestCase):
    def test_context_contains_customer_orders_and_interactions(self):
        customer = make_customer(name="Trần Thị Bình", company="Bình An Co")
        order = make_order(customer, Order.Status.COMPLETED, [("Máy in hoá đơn", 2, 1350000)])
        InteractionLog.objects.create(customer=customer, customer_message="Máy in bị mờ")
        context = GeminiCRMService().build_customer_context(customer)
        for expected in ["Trần Thị Bình", "Bình An Co", "Tiềm năng", order.code, "Máy in hoá đơn", "2.700.000 ₫", "Máy in bị mờ"]:
            self.assertIn(expected, context)


@override_settings(**LIVE)
class SuggestReplyLiveTests(TestCase):
    def setUp(self):
        self.customer = make_customer(name="Lê Hoàng Cường")
        make_order(self.customer, items=[("Thiết kế website", 1, 9500000)])
        self.service = GeminiCRMService()

    def test_prompt_contains_customer_data_message_and_tone(self):
        client = fake_client("Chào anh Cường ...")
        with patch_client(client):
            reply = self.service.suggest_reply(self.customer, "Có giảm giá không?", tone="trang trọng")

        self.assertEqual(reply, "Chào anh Cường ...")
        kwargs = client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-3.8-flash")
        prompt = kwargs["contents"]
        for expected in ["Lê Hoàng Cường", "Thiết kế website", "Có giảm giá không?", "trang trọng", "không bịa"]:
            self.assertIn(expected, prompt)

    def test_sdk_exception_is_wrapped_in_ai_service_error(self):
        client = mock.MagicMock()
        client.models.generate_content.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED quota")
        with patch_client(client), self.assertLogs("crm.services.ai_service", level="ERROR"):
            with self.assertRaises(AIServiceError) as ctx:
                self.service.suggest_reply(self.customer, "Xin chào")
        self.assertIn("quota", str(ctx.exception))
        self.assertNotIn("test-key-khong-that", str(ctx.exception))

    @override_settings(GEMINI_FALLBACK_MODEL="gemini-flash-latest")
    def test_overloaded_model_falls_back_to_backup_model(self):
        client = mock.MagicMock()
        client.models.generate_content.side_effect = [
            RuntimeError("503 UNAVAILABLE high demand"),
            mock.MagicMock(text="Email từ model dự phòng"),
        ]
        with patch_client(client), self.assertLogs("crm.services.ai_service", level="WARNING"):
            reply = self.service.suggest_reply(self.customer, "Xin chào")
        self.assertEqual(reply, "Email từ model dự phòng")
        used = [c.kwargs["model"] for c in client.models.generate_content.call_args_list]
        self.assertEqual(used, ["gemini-3.8-flash", "gemini-flash-latest"])

    @override_settings(GEMINI_FALLBACK_MODEL="gemini-flash-latest")
    def test_non_temporary_error_does_not_fall_back(self):
        client = mock.MagicMock()
        client.models.generate_content.side_effect = RuntimeError("400 API key not valid")
        with patch_client(client), self.assertLogs("crm.services.ai_service", level="ERROR"):
            with self.assertRaises(AIServiceError) as ctx:
                self.service.suggest_reply(self.customer, "Xin chào")
        self.assertEqual(client.models.generate_content.call_count, 1)
        self.assertIn("API key", str(ctx.exception))

    def test_empty_response_raises_ai_service_error(self):
        with patch_client(fake_client("")), self.assertLogs("crm.services.ai_service", level="WARNING"):
            with self.assertRaises(AIServiceError):
                self.service.suggest_reply(self.customer, "Xin chào")

    def test_generate_with_json_schema_sets_json_mime_type(self):
        client = fake_client('{"a": 1}')
        schema = {"type": "OBJECT", "properties": {"a": {"type": "INTEGER"}}}
        with patch_client(client):
            self.service._generate("prompt", json_schema=schema)
        config = client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertIsNotNone(config.response_schema)

    def test_client_is_created_lazily_once(self):
        with mock.patch("google.genai.Client") as client_cls:
            service = GeminiCRMService()
            client_cls.assert_not_called()
            first = service.client
            second = service.client
        client_cls.assert_called_once_with(api_key="test-key-khong-that")
        self.assertIs(first, second)


class MockModeTests(TestCase):
    @override_settings(GEMINI_API_KEY="", FALLBACK_AI_API_KEY="", AI_MOCK=False)
    def test_mock_mode_when_api_key_missing(self):
        service = GeminiCRMService()
        self.assertTrue(service.is_mock)
        with mock.patch("google.genai.Client") as client_cls:
            reply = service.suggest_reply(make_customer(name="Phạm Thu Dung"), "Có dùng thử không?")
        client_cls.assert_not_called()
        self.assertIn("Phạm Thu Dung", reply)

    @override_settings(GEMINI_API_KEY="co-key", AI_MOCK=True)
    def test_mock_mode_when_ai_mock_enabled(self):
        self.assertTrue(GeminiCRMService().is_mock)

    @override_settings(GEMINI_API_KEY="co-key", AI_MOCK=False)
    def test_live_mode_when_key_present(self):
        self.assertFalse(GeminiCRMService().is_mock)

    def test_get_ai_service_returns_shared_instance(self):
        self.assertIs(get_ai_service(), get_ai_service())


FALLBACK = {
    **LIVE,
    "FALLBACK_AI_API_KEY": "fallback-key-khong-that",
    "FALLBACK_AI_BASE_URL": "https://api.groq.com/openai/v1/",
    "FALLBACK_AI_MODEL": "llama-3.3-70b-versatile",
    "FALLBACK_AI_NAME": "Groq Llama 3.3",
}


def http_response(status=200, content="Email từ AI dự phòng"):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]}, request=request)


def failing_gemini(message="503 UNAVAILABLE high demand"):
    client = mock.MagicMock()
    client.models.generate_content.side_effect = RuntimeError(message)
    return client


@override_settings(**FALLBACK)
class FallbackProviderTests(TestCase):
    def setUp(self):
        self.customer = make_customer(name="Đỗ Mạnh Khang")
        self.service = GeminiCRMService()

    def test_gemini_failure_switches_to_openai_compatible_provider(self):
        with patch_client(failing_gemini()), mock.patch("httpx.post", return_value=http_response()) as post, \
                self.assertLogs("crm.services.ai_service", level="WARNING"):
            reply = self.service.suggest_reply(self.customer, "Khi nào kích hoạt tài khoản?")

        self.assertEqual(reply, "Email từ AI dự phòng")
        self.assertEqual(self.service.last_provider_label, "Groq Llama 3.3")
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertEqual(url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer fallback-key-khong-that")
        self.assertEqual(kwargs["json"]["model"], "llama-3.3-70b-versatile")
        self.assertIn("Đỗ Mạnh Khang", kwargs["json"]["messages"][0]["content"])

    @override_settings(GEMINI_API_KEY="")
    def test_only_fallback_key_uses_provider_directly(self):
        self.assertFalse(self.service.is_mock)
        with mock.patch("google.genai.Client") as client_cls, \
                mock.patch("httpx.post", return_value=http_response()):
            self.service.suggest_reply(self.customer, "Xin chào")
        client_cls.assert_not_called()
        self.assertEqual(self.service.last_provider_label, "Groq Llama 3.3")

    def test_gemini_success_does_not_call_fallback(self):
        with patch_client(fake_client("Email từ Gemini")), mock.patch("httpx.post") as post:
            reply = self.service.suggest_reply(self.customer, "Xin chào")
        post.assert_not_called()
        self.assertEqual(reply, "Email từ Gemini")
        self.assertEqual(self.service.last_provider_label, "AI Gemini")

    def test_both_providers_fail_raise_combined_error(self):
        with patch_client(failing_gemini()), mock.patch("httpx.post", return_value=http_response(402)), \
                self.assertLogs("crm.services.ai_service", level="WARNING"):
            with self.assertRaises(AIServiceError) as ctx:
                self.service.suggest_reply(self.customer, "Xin chào")
        message = str(ctx.exception)
        self.assertIn("Cả Gemini và AI dự phòng đều đang lỗi", message)
        self.assertIn("hết số dư", message)
        self.assertNotIn("fallback-key-khong-that", message)

    def test_network_error_and_think_tags(self):
        with mock.patch("httpx.post", side_effect=httpx.ConnectError("boom")), \
                self.assertLogs("crm.services.ai_service", level="ERROR"):
            with self.assertRaises(AIServiceError):
                self.service._generate_openai_compatible("prompt")
        with mock.patch("httpx.post", return_value=http_response(content="<think>nháp</think>\nEmail cuối")):
            self.assertEqual(self.service._generate_openai_compatible("prompt"), "Email cuối")

    def test_json_schema_requests_json_object(self):
        schema = {"type": "OBJECT", "properties": {"segment": {"type": "STRING"}}}
        with mock.patch("httpx.post", return_value=http_response(content='{"segment": "VIP"}')) as post:
            self.service._generate_openai_compatible("Phân loại", json_schema=schema)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertIn('"segment"', payload["messages"][0]["content"])

class ClassifyCustomerTests(TestCase):
    def setUp(self):
        self.service = GeminiCRMService()

    @override_settings(AI_MOCK=True)
    def test_mock_classification_churned_is_high_priority(self):
        customer = make_customer(status="churned")
        result = self.service.analyze_customer(customer)
        self.assertEqual(result["sentiment"], "negative")
        self.assertEqual(result["priority"], "high")
        self.assertEqual(customer.ai_priority, "high")
        self.assertIsNotNone(customer.ai_analyzed_at)

    def test_safe_defaults_when_ai_returns_invalid_data(self):
        customer = make_customer(status="caring")
        # Giả lập _generate_live trả về JSON thiếu/sai
        with patch_client(fake_client('{"sentiment": "super_happy", "priority": "urgent", "suggested_status": "unknown"}')):
            result = self.service._analyze_customer_live(customer)
        self.assertEqual(result["sentiment"], "neutral")  # fallback
        self.assertEqual(result["priority"], "medium")   # fallback
        self.assertEqual(result["suggested_status"], "caring") # fallback to current status

    @override_settings(AI_MOCK=True)
    def test_mock_classification_format(self):
        customer = make_customer(status="lead")
        make_order(customer)
        result = self.service.analyze_customer(customer)
        self.assertIn("sentiment", result)
        self.assertIn("priority", result)
        self.assertIn("suggested_status", result)
        self.assertIn("summary", result)
        self.assertIsInstance(result["next_actions"], list)


class ReportStatsTests(TestCase):
    def setUp(self):
        self.service = GeminiCRMService()

    def test_build_report_stats_calculates_revenue_correctly(self):
        customer = make_customer()
        # Đơn hoàn thành -> doanh thu
        make_order(customer, status=Order.Status.COMPLETED, items=[("SP1", 2, 100000), ("SP2", 1, 50000)]) # 250k
        make_order(customer, status=Order.Status.COMPLETED, items=[("SP3", 1, 300000)]) # 300k
        # Đơn huỷ -> không tính
        make_order(customer, status=Order.Status.CANCELLED, items=[("SP4", 1, 1000000)])

        stats = self.service.build_report_stats()
        self.assertEqual(stats["revenue"], 550000)
        self.assertEqual(stats["total_customers"], 1)

    @override_settings(AI_MOCK=True)
    def test_mock_report_generation(self):
        customer = make_customer()
        make_order(customer, status=Order.Status.COMPLETED, items=[("SP1", 1, 100000)])
        
        result = self.service.generate_report()
        self.assertIn("stats", result)
        self.assertIn("insight", result)
        self.assertIn("TÌNH HÌNH CHUNG", result["insight"])
        self.assertIn("100.000", result["insight"])

