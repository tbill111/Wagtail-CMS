from unittest import mock

from django.test import TestCase, override_settings

from crm.models import InteractionLog, Order
from crm.services.ai_service import AIServiceError, GeminiCRMService, get_ai_service

from .factories import make_customer, make_order

LIVE = {"GEMINI_API_KEY": "test-key-khong-that", "AI_MOCK": False, "GEMINI_MODEL": "gemini-2.5-flash"}


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
        self.assertEqual(kwargs["model"], "gemini-2.5-flash")
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
    @override_settings(GEMINI_API_KEY="", AI_MOCK=False)
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
