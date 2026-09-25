"""Dịch vụ AI của SmartCRM – bọc Google Gemini (SDK ``google-genai``).

Mọi logic gọi Gemini nằm ở đây, views chỉ gọi các method công khai.
Để thêm tính năng AI mới: viết method mới dùng lại ``build_customer_context``
và ``_generate`` (xem README – "Hướng dẫn mở rộng tính năng AI").
"""

import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

ALLOWED_TONES = ("lịch sự", "thân thiện", "trang trọng")
DEFAULT_TONE = "lịch sự"


class AIServiceError(Exception):
    """Lỗi khi gọi AI – ``str(error)`` là thông điệp tiếng Việt hiển thị được cho người dùng."""

    default_message = "Trợ lý AI tạm thời không phản hồi. Vui lòng thử lại sau ít phút."

    def __init__(self, message=None):
        super().__init__(message or self.default_message)


def format_vnd(amount):
    return f"{int(amount or 0):,}".replace(",", ".") + " ₫"


class GeminiCRMService:
    def __init__(self):
        self._client = None
        self._client_key = None

    # ------------------------------------------------------------------ cấu hình
    @property
    def api_key(self):
        return getattr(settings, "GEMINI_API_KEY", "") or ""

    @property
    def model_name(self):
        return getattr(settings, "GEMINI_MODEL", "") or "gemini-3.8-flash"

    @property
    def is_mock(self):
        """Chế độ mô phỏng: không có API key hoặc AI_MOCK=True."""
        return bool(getattr(settings, "AI_MOCK", False)) or not self.api_key

    @property
    def client(self):
        """Khởi tạo client Gemini một lần (lazy), tạo lại nếu API key thay đổi."""
        if self._client is None or self._client_key != self.api_key:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            self._client_key = self.api_key
        return self._client

    # ------------------------------------------------------------- dùng chung
    def build_customer_context(self, customer):
        """Tóm tắt dữ liệu khách hàng trong CSDL thành văn bản để đưa vào prompt."""
        lines = [
            "THÔNG TIN KHÁCH HÀNG",
            f"- Họ tên: {customer.name}",
            f"- Email: {customer.email}",
            f"- Số điện thoại: {customer.phone or 'không có'}",
            f"- Công ty: {customer.company or 'không có'}",
            f"- Trạng thái: {customer.get_status_display()}",
            f"- Nguồn: {customer.get_source_display()}",
            f"- Tổng chi tiêu (đơn hoàn thành): {format_vnd(customer.total_spent)}",
        ]

        orders = list(customer.orders.prefetch_related("items").order_by("-created_at")[:5])
        lines.append("")
        lines.append("5 ĐƠN HÀNG GẦN NHẤT")
        if orders:
            for order in orders:
                products = ", ".join(
                    f"{item.product_name} x{item.quantity}" for item in order.items.all()
                ) or "không có sản phẩm"
                lines.append(
                    f"- {order.code} ({timezone.localtime(order.created_at):%d/%m/%Y}) – "
                    f"{order.get_status_display()} – {format_vnd(order.total_amount)} – {products}"
                )
        else:
            lines.append("- Chưa có đơn hàng")

        interactions = list(customer.interactions.order_by("-created_at")[:5])
        lines.append("")
        lines.append("5 TƯƠNG TÁC GẦN NHẤT")
        if interactions:
            for log in interactions:
                reply = (log.final_reply or "").strip().replace("\n", " ")
                lines.append(
                    f"- [{timezone.localtime(log.created_at):%d/%m/%Y}] ({log.get_channel_display()}) "
                    f"Khách: {log.customer_message.strip()[:300]}"
                    + (f" | Đã phản hồi: {reply[:200]}" if reply else "")
                )
        else:
            lines.append("- Chưa có tương tác")

        return "\n".join(lines)

    @property
    def fallback_model_name(self):
        return getattr(settings, "GEMINI_FALLBACK_MODEL", "") or ""

    @staticmethod
    def _is_temporary_error(exc):
        """Lỗi phía máy chủ Google (quá tải, 5xx) – nên thử lại bằng model dự phòng."""
        raw = str(exc).lower()
        return any(k in raw for k in ("503", "unavailable", "overloaded", "high demand", "500", "internal"))

    def _generate(self, prompt, *, json_schema=None):
        """Gọi Gemini và trả về văn bản. Mọi lỗi được chuyển thành ``AIServiceError``.

        Nếu model chính quá tải (503) sẽ tự thử lại một lần với ``GEMINI_FALLBACK_MODEL``.
        """
        from google.genai import types

        config_kwargs = {
            "temperature": 0.7,
            # Không dùng function calling -> tắt AFC để tránh cảnh báo của SDK
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if json_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = json_schema

        models = [self.model_name]
        if self.fallback_model_name and self.fallback_model_name != self.model_name:
            models.append(self.fallback_model_name)

        for index, model in enumerate(models):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                text = (getattr(response, "text", None) or "").strip()
            except Exception as exc:  # noqa: BLE001 – gom mọi lỗi của SDK/mạng
                # Chỉ ghi loại lỗi + model, không bao giờ ghi API key
                has_next = index + 1 < len(models)
                if has_next and self._is_temporary_error(exc):
                    logger.warning("Gemini quá tải (model=%s), thử model dự phòng %s", model, models[index + 1])
                    continue
                logger.error("Gọi Gemini thất bại (model=%s): %s", model, type(exc).__name__)
                raise AIServiceError(self._friendly_message(exc)) from exc

            if not text:
                logger.warning("Gemini trả về nội dung rỗng (model=%s)", model)
                raise AIServiceError("AI không trả về nội dung. Vui lòng thử lại.")
            return text

    @staticmethod
    def _friendly_message(exc):
        raw = str(exc).lower()
        if "api key" in raw or "api_key" in raw or "permission" in raw or "401" in raw or "403" in raw:
            return "API key Gemini không hợp lệ hoặc chưa được cấp quyền. Vui lòng kiểm tra GEMINI_API_KEY."
        if "quota" in raw or "429" in raw or "resource_exhausted" in raw:
            return "Đã hết hạn mức (quota) gọi Gemini. Vui lòng thử lại sau hoặc bật chế độ mô phỏng."
        if "not found" in raw or "404" in raw:
            return "Không tìm thấy model Gemini đã cấu hình. Vui lòng kiểm tra GEMINI_MODEL."
        if GeminiCRMService._is_temporary_error(exc):
            return "Máy chủ Gemini đang quá tải. Vui lòng thử lại sau ít giây hoặc bật chế độ mô phỏng."
        return AIServiceError.default_message

    # --------------------------------------------------------- tính năng AI
    def suggest_reply(self, customer, message, tone=DEFAULT_TONE):
        """Gợi ý email phản hồi tin nhắn của khách, dựa trên dữ liệu CRM."""
        if tone not in ALLOWED_TONES:
            tone = DEFAULT_TONE
        message = (message or "").strip()

        if self.is_mock:
            return self._mock_reply(customer, message, tone)

        prompt = f"""Bạn là nhân viên chăm sóc khách hàng của doanh nghiệp đang dùng hệ thống SmartCRM.
Nhiệm vụ: viết MỘT email phản hồi bằng tiếng Việt cho tin nhắn mới nhất của khách hàng.

YÊU CẦU:
- Giọng văn: {tone}.
- Cấu trúc: lời chào có tên khách → nội dung trả lời đúng trọng tâm → lời kết và ký tên "Bộ phận Chăm sóc khách hàng".
- Ngắn gọn (khoảng 80–180 từ), không dùng markdown, không thêm tiêu đề "Subject".
- Chỉ dùng thông tin có trong dữ liệu bên dưới. TUYỆT ĐỐI không bịa giá, khuyến mãi, chính sách,
  thời hạn hay cam kết không có trong dữ liệu; nếu thiếu thông tin hãy hẹn kiểm tra và phản hồi lại.

{self.build_customer_context(customer)}

TIN NHẮN MỚI CỦA KHÁCH:
\"\"\"{message}\"\"\"

Chỉ trả về nội dung email."""
        return self._generate(prompt)

    @staticmethod
    def _mock_reply(customer, message, tone):
        greeting = {
            "thân thiện": f"Chào {customer.name},",
            "trang trọng": f"Kính gửi Quý khách {customer.name},",
        }.get(tone, f"Kính chào anh/chị {customer.name},")
        excerpt = message[:120] + ("…" if len(message) > 120 else "")
        return (
            f"{greeting}\n\n"
            f"Cảm ơn anh/chị đã liên hệ với chúng tôi. Chúng tôi đã nhận được nội dung: “{excerpt}”.\n"
            "Bộ phận phụ trách đang kiểm tra thông tin và sẽ phản hồi chi tiết cho anh/chị "
            "trong thời gian sớm nhất.\n\n"
            "Nếu cần hỗ trợ gấp, anh/chị vui lòng trả lời email này hoặc gọi cho nhân viên phụ trách.\n\n"
            "Trân trọng,\nBộ phận Chăm sóc khách hàng"
        )


_service = None


def get_ai_service():
    """Trả về instance ``GeminiCRMService`` dùng chung trong toàn ứng dụng."""
    global _service
    if _service is None:
        _service = GeminiCRMService()
    return _service
