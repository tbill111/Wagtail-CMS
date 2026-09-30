import json
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


def classify_json(**overrides):
    data = {
        "sentiment": "negative",
        "priority": "high",
        "suggested_status": "caring",
        "summary": "Khách phàn nàn máy in bị mờ.",
        "next_actions": ["Gọi lại cho khách", "Gửi kỹ thuật"],
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


@override_settings(**LIVE)
class AnalyzeCustomerLiveTests(TestCase):
    def setUp(self):
        self.customer = make_customer(name="Trần Thị Bình", status="lead")
        make_order(self.customer, Order.Status.COMPLETED, [("Máy in hoá đơn", 1, 1350000)])
        InteractionLog.objects.create(customer=self.customer, customer_message="Máy in bị mờ, rất bực mình")
        self.service = GeminiCRMService()

    def analyze(self, text):
        client = fake_client(text)
        with patch_client(client):
            result = self.service.analyze_customer(self.customer)
        return result, client

    def test_prompt_contains_customer_data_and_uses_schema(self):
        _, client = self.analyze(classify_json())
        kwargs = client.models.generate_content.call_args.kwargs
        for expected in ["Trần Thị Bình", "Máy in hoá đơn", "Máy in bị mờ", "không bịa"]:
            self.assertIn(expected, kwargs["contents"])
        self.assertEqual(kwargs["config"].response_mime_type, "application/json")

    def test_valid_json_saves_ai_fields_without_changing_status(self):
        result, _ = self.analyze(classify_json())
        self.assertEqual(result["priority"], "high")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.ai_sentiment, "negative")
        self.assertEqual(self.customer.ai_priority, "high")
        self.assertEqual(self.customer.ai_suggested_status, "caring")
        self.assertEqual(self.customer.ai_summary, "Khách phàn nàn máy in bị mờ.")
        self.assertEqual(self.customer.ai_next_actions, ["Gọi lại cho khách", "Gửi kỹ thuật"])
        self.assertEqual(self.customer.ai_provider, "AI Gemini")
        self.assertIsNotNone(self.customer.ai_analyzed_at)
        self.assertEqual(self.customer.status, "lead")

    def test_invalid_json_raises_ai_service_error(self):
        with self.assertRaises(AIServiceError) as ctx:
            self.analyze("Đây không phải JSON")
        self.assertIn("JSON", str(ctx.exception))
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.ai_analyzed_at)

    def test_unknown_or_wrong_type_values_fall_back_to_safe_defaults(self):
        result, _ = self.analyze(classify_json(
            sentiment=["positive"], priority="urgent", suggested_status="vip", summary=None, next_actions="gọi lại"
        ))
        self.assertEqual(result["sentiment"], "neutral")
        self.assertEqual(result["priority"], "medium")
        self.assertEqual(result["suggested_status"], "lead")  # giữ nguyên trạng thái hiện tại
        self.assertEqual(result["summary"], "")
        self.assertEqual(result["next_actions"], [])

    def test_next_actions_are_cut_to_three_strings(self):
        result, _ = self.analyze(classify_json(next_actions=["A1", 2, " ", "A3", "A4", "A5"]))
        self.assertEqual(result["next_actions"], ["A1", "2", "A3"])

    def test_json_wrapped_in_markdown_fence_with_leading_text(self):
        result, _ = self.analyze("Đây là kết quả:\n```json\n" + classify_json(priority="low") + "\n```")
        self.assertEqual(result["priority"], "low")
        result, _ = self.analyze("Kết quả: " + classify_json(priority="medium") + " Hết.")
        self.assertEqual(result["priority"], "medium")

    @override_settings(**FALLBACK)
    @override_settings(GEMINI_API_KEY="")
    def test_fallback_provider_json_is_parsed_and_labelled(self):
        content = "```json\n" + classify_json(sentiment="positive") + "\n```"
        with mock.patch("httpx.post", return_value=http_response(content=content)) as post:
            result = self.service.analyze_customer(self.customer)
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(result["sentiment"], "positive")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.ai_provider, "Groq Llama 3.3")


@override_settings(AI_MOCK=True)
class AnalyzeCustomerMockTests(TestCase):
    def test_mock_returns_valid_structure_without_calling_ai(self):
        customer = make_customer(status="churned")
        client = mock.MagicMock()
        with patch_client(client), mock.patch("httpx.post") as post:
            result = GeminiCRMService().analyze_customer(customer)
        client.models.generate_content.assert_not_called()
        post.assert_not_called()
        self.assertEqual((result["sentiment"], result["priority"]), ("negative", "high"))
        self.assertLessEqual(len(result["next_actions"]), 3)
        customer.refresh_from_db()
        self.assertEqual(customer.ai_provider, "AI Gemini (chế độ mô phỏng)")
        self.assertEqual(customer.status, "churned")


class ReportStatsTests(TestCase):
    def setUp(self):
        self.an = make_customer(name="An", email="an@example.com", status="customer", ai_sentiment="positive")
        self.binh = make_customer(name="Bình", email="binh@example.com", status="churned", ai_sentiment="negative")
        make_customer(name="Cường", email="cuong@example.com")
        make_order(self.an, Order.Status.COMPLETED, [("SP1", 2, 100000), ("SP2", 1, 50000)])  # 250.000
        make_order(self.binh, Order.Status.COMPLETED, [("SP3", 1, 300000)])  # 300.000
        make_order(self.an, Order.Status.CANCELLED, [("SP4", 1, 1000000)])  # không tính
        make_order(self.an, Order.Status.PROCESSING, [("SP5", 1, 70000)])  # không tính

    def test_stats_match_database_and_are_json_serializable(self):
        stats = GeminiCRMService.build_report_stats()
        json.dumps(stats)  # không có Decimal/datetime -> lưu JSONField được
        self.assertEqual(stats["total_customers"], 3)
        self.assertEqual(stats["new_customers_month"], 3)
        self.assertEqual(stats["revenue"], 550000)
        self.assertEqual(stats["customers_by_status"]["lead"]["count"], 1)
        self.assertEqual(stats["customers_by_status"]["churned"]["count"], 1)
        self.assertEqual(stats["orders_by_status"]["completed"]["count"], 2)
        self.assertEqual(stats["orders_by_status"]["cancelled"]["count"], 1)
        self.assertEqual(stats["top_customers"], [{"name": "Bình", "spent": 300000}, {"name": "An", "spent": 250000}])
        self.assertEqual(stats["sentiment_counts"]["negative"]["count"], 1)
        self.assertEqual(stats["analyzed_count"], 2)

    @override_settings(**LIVE)
    def test_live_report_sends_stats_to_ai(self):
        client = fake_client("TÌNH HÌNH CHUNG\n- ...")
        with patch_client(client):
            result = GeminiCRMService().generate_report()
        prompt = client.models.generate_content.call_args.kwargs["contents"]
        for expected in ['"revenue": 550000', "RỦI RO CẦN CHÚ Ý", "không bịa"]:
            self.assertIn(expected, prompt)
        self.assertEqual(result["insight"], "TÌNH HÌNH CHUNG\n- ...")
        self.assertIn("generated_at", result)

    @override_settings(AI_MOCK=True)
    def test_mock_report_only_uses_real_stats(self):
        insight = GeminiCRMService().generate_report()["insight"]
        for expected in ["TÌNH HÌNH CHUNG", "RỦI RO CẦN CHÚ Ý", "ĐỀ XUẤT HÀNH ĐỘNG", "550.000 ₫", "1 đơn hàng bị huỷ"]:
            self.assertIn(expected, insight)
        self.assertNotIn("chưa được phản hồi", insight)
