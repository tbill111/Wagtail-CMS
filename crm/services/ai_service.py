"""Dịch vụ AI của SmartCRM – bọc Google Gemini (SDK ``google-genai``).

AI chính là Gemini. Có thể cấu hình thêm một nhà cung cấp AI dự phòng theo chuẩn
API tương thích OpenAI (Groq, OpenRouter, DeepSeek…), được dùng khi Gemini lỗi.
Mọi logic gọi AI nằm ở đây, views chỉ gọi các method công khai.
Để thêm tính năng AI mới: viết method mới dùng lại ``build_customer_context``
và ``_generate`` (xem README – "Hướng dẫn mở rộng tính năng AI").
"""

import json
import logging
import re
import threading

import httpx
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
        # Lưu nhà cung cấp đã trả lời lần gọi gần nhất, riêng cho từng luồng (request)
        self._state = threading.local()

    # ------------------------------------------------------------------ cấu hình
    @property
    def api_key(self):
        return getattr(settings, "GEMINI_API_KEY", "") or ""

    @property
    def model_name(self):
        return getattr(settings, "GEMINI_MODEL", "") or "gemini-3.8-flash"

    @property
    def fallback_api_key(self):
        return getattr(settings, "FALLBACK_AI_API_KEY", "") or ""

    @property
    def fallback_base_url(self):
        return (getattr(settings, "FALLBACK_AI_BASE_URL", "") or "").rstrip("/")

    @property
    def fallback_provider_model(self):
        return getattr(settings, "FALLBACK_AI_MODEL", "") or ""

    @property
    def fallback_provider_name(self):
        return getattr(settings, "FALLBACK_AI_NAME", "") or "AI dự phòng"

    @property
    def has_fallback_provider(self):
        """Đã cấu hình đủ nhà cung cấp dự phòng (tương thích OpenAI) hay chưa."""
        return bool(self.fallback_api_key and self.fallback_base_url and self.fallback_provider_model)

    @property
    def is_mock(self):
        """Chế độ mô phỏng: AI_MOCK=True, hoặc không có key Gemini lẫn key AI dự phòng."""
        if getattr(settings, "AI_MOCK", False):
            return True
        return not self.api_key and not self.has_fallback_provider

    @property
    def last_provider_label(self):
        """Tên AI đã trả lời lần gọi gần nhất trong luồng hiện tại (hiển thị trên giao diện)."""
        return getattr(self._state, "provider", "AI Gemini")

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
        """Gọi AI và trả về văn bản. Mọi lỗi được chuyển thành ``AIServiceError``.

        Thứ tự thử: Gemini (model chính, rồi ``GEMINI_FALLBACK_MODEL`` khi quá tải),
        sau đó nhà cung cấp dự phòng tương thích OpenAI (nếu đã cấu hình ``FALLBACK_AI_*``).
        """
        gemini_error = None
        if self.api_key:
            try:
                text = self._generate_gemini(prompt, json_schema=json_schema)
                self._state.provider = "AI Gemini"
                return text
            except AIServiceError as exc:
                if not self.has_fallback_provider:
                    raise
                gemini_error = exc
                logger.warning("Gemini lỗi, chuyển sang %s", self.fallback_provider_name)

        try:
            text = self._generate_openai_compatible(prompt, json_schema=json_schema)
        except AIServiceError as exc:
            if gemini_error is not None:
                raise AIServiceError(
                    "Cả Gemini và AI dự phòng đều đang lỗi. "
                    f"Gemini: {gemini_error} | {self.fallback_provider_name}: {exc}"
                ) from exc
            raise
        self._state.provider = self.fallback_provider_name
        return text

    def _generate_gemini(self, prompt, *, json_schema=None):
        """Gọi Gemini; nếu model chính quá tải (503) thì thử lại với ``GEMINI_FALLBACK_MODEL``."""
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

    def _generate_openai_compatible(self, prompt, *, json_schema=None):
        """Gọi nhà cung cấp dự phòng theo chuẩn OpenAI Chat Completions (Groq, OpenRouter, DeepSeek…)."""
        name = self.fallback_provider_name
        content = prompt
        payload = {"model": self.fallback_provider_model, "temperature": 0.7}
        if json_schema is not None:
            payload["response_format"] = {"type": "json_object"}
            content = (
                f"{prompt}\n\nChỉ trả về một đối tượng JSON hợp lệ theo schema sau:\n"
                f"{json.dumps(json_schema, ensure_ascii=False)}"
            )
        payload["messages"] = [{"role": "user", "content": content}]
        try:
            response = httpx.post(
                f"{self.fallback_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.fallback_api_key}",
                    "X-Title": "SmartCRM",  # OpenRouter dùng để hiển thị tên ứng dụng
                },
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"] or ""
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logger.error("Gọi %s thất bại (model=%s): HTTP %s", name, self.fallback_provider_model, status)
            raise AIServiceError(self._friendly_fallback_message(status)) from exc
        except Exception as exc:  # noqa: BLE001 – lỗi mạng, JSON sai định dạng…
            logger.error("Gọi %s thất bại (model=%s): %s", name, self.fallback_provider_model, type(exc).__name__)
            raise AIServiceError(f"Không kết nối được {name}. Vui lòng thử lại sau.") from exc

        # Một số model suy luận (ví dụ DeepSeek R1) trả kèm phần <think>…</think>
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        if not text:
            logger.warning("%s trả về nội dung rỗng (model=%s)", name, self.fallback_provider_model)
            raise AIServiceError("AI không trả về nội dung. Vui lòng thử lại.")
        return text

    def _friendly_fallback_message(self, status):
        name = self.fallback_provider_name
        if status in (401, 403):
            return f"API key của {name} không hợp lệ. Vui lòng kiểm tra FALLBACK_AI_API_KEY."
        if status == 402:
            return f"Tài khoản {name} đã hết số dư. Vui lòng nạp thêm hoặc dùng nhà cung cấp miễn phí khác."
        if status == 429:
            return f"Đã hết hạn mức (quota) gọi {name}. Vui lòng thử lại sau."
        if status in (400, 404):
            return f"Model của {name} không tồn tại hoặc không hợp lệ. Vui lòng kiểm tra FALLBACK_AI_MODEL."
        return f"{name} đang quá tải hoặc gặp sự cố. Vui lòng thử lại sau."

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
            self._state.provider = "AI Gemini"
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

    # ------------------------------------------------ Phân loại khách hàng AI
    _CLASSIFY_SCHEMA = {
        "type": "OBJECT",
        "properties": {
            "sentiment": {"type": "STRING", "enum": ["positive", "neutral", "negative"]},
            "priority": {"type": "STRING", "enum": ["high", "medium", "low"]},
            "suggested_status": {
                "type": "STRING",
                "enum": ["lead", "caring", "customer", "churned"],
            },
            "summary": {"type": "STRING"},
            "next_actions": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
        "required": ["sentiment", "priority", "suggested_status", "summary", "next_actions"],
    }
    ANALYSIS_FIELDS = [
        "ai_sentiment", "ai_priority", "ai_suggested_status",
        "ai_summary", "ai_next_actions", "ai_analyzed_at", "ai_provider",
    ]

    def analyze_customer(self, customer):
        """Phân loại khách hàng bằng AI rồi lưu các trường ``ai_*``. Không tự đổi ``status``."""
        if self.is_mock:
            self._state.provider = "AI Gemini"
            result = self._mock_analysis(customer)
            provider = f"{self.last_provider_label} (chế độ mô phỏng)"
        else:
            result = self._analyze_customer_live(customer)
            provider = self.last_provider_label
        self.save_analysis(customer, result, provider)
        return result

    @classmethod
    def save_analysis(cls, customer, result, provider):
        """Ghi kết quả phân loại (đã validate) vào khách hàng – dùng chung cho API và ``seed_demo``."""
        customer.ai_sentiment = result["sentiment"]
        customer.ai_priority = result["priority"]
        customer.ai_suggested_status = result["suggested_status"]
        customer.ai_summary = result["summary"]
        customer.ai_next_actions = result["next_actions"]
        customer.ai_analyzed_at = timezone.now()
        customer.ai_provider = provider
        customer.save(update_fields=cls.ANALYSIS_FIELDS)

    def _analyze_customer_live(self, customer):
        """Gọi AI thật để phân tích khách hàng, validate kết quả."""
        from crm.models import Customer

        prompt = f"""Bạn là chuyên gia phân tích CRM. Hãy phân tích khách hàng sau và trả về JSON.

{self.build_customer_context(customer)}

YÊU CẦU:
1. sentiment: cảm xúc của khách qua lịch sử tương tác (positive / neutral / negative).
2. priority: mức ưu tiên chăm sóc (high / medium / low).
3. suggested_status: trạng thái nên chuyển sang (lead = Tiềm năng, caring = Đang chăm sóc,
   customer = Đã mua hàng, churned = Đã rời bỏ); giữ nguyên nếu không cần đổi.
4. summary: tóm tắt tối đa 3 câu tiếng Việt.
5. next_actions: danh sách tối đa 3 hành động cụ thể nên làm, bằng tiếng Việt.

Chỉ dùng thông tin trong dữ liệu. TUYỆT ĐỐI không bịa thêm.
Trả về đúng một JSON object."""

        data = self._parse_json_safe(self._generate(prompt, json_schema=self._CLASSIFY_SCHEMA))

        next_actions = data.get("next_actions")
        if not isinstance(next_actions, list):
            next_actions = []
        next_actions = [str(a).strip() for a in next_actions if str(a).strip()][:3]
        summary = data.get("summary")

        return {
            "sentiment": self._pick_choice(data.get("sentiment"), Customer.Sentiment.values, "neutral"),
            "priority": self._pick_choice(data.get("priority"), Customer.Priority.values, "medium"),
            "suggested_status": self._pick_choice(
                data.get("suggested_status"), Customer.Status.values, customer.status
            ),
            "summary": summary.strip()[:500] if isinstance(summary, str) else "",
            "next_actions": next_actions,
        }

    @staticmethod
    def _pick_choice(value, allowed, default):
        """Giá trị AI trả về nếu hợp lệ, ngược lại dùng giá trị mặc định an toàn."""
        value = value.strip().lower() if isinstance(value, str) else ""
        return value if value in allowed else default

    @staticmethod
    def _parse_json_safe(text):
        """Parse JSON từ AI, chịu được ```json … ``` hoặc lời dẫn trước/sau đối tượng JSON."""
        text = (text or "").strip()
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1)
        elif not text.startswith("{"):
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                text = text[start:end + 1]
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise AIServiceError(
                "AI trả về dữ liệu không đúng định dạng JSON. Vui lòng thử lại."
            ) from exc
        if not isinstance(data, dict):
            raise AIServiceError("AI trả về dữ liệu không đúng cấu trúc. Vui lòng thử lại.")
        return data

    @staticmethod
    def _mock_analysis(customer):
        """Kết quả phân tích giả lập hợp lý, suy từ đơn hàng/tương tác (dùng cho MOCK và ``seed_demo``)."""
        order_count = customer.orders.count()
        interaction_count = customer.interactions.count()
        total_spent = int(customer.total_spent)

        if customer.status == "churned":
            sentiment = "negative"
        elif total_spent > 5_000_000 or interaction_count > 2:
            sentiment = "positive"
        else:
            sentiment = "neutral"

        if total_spent > 10_000_000 or customer.status == "churned":
            priority = "high"
        elif order_count >= 2:
            priority = "medium"
        else:
            priority = "low"

        if customer.status == "lead" and interaction_count >= 2:
            suggested_status = "caring"
        elif customer.status in ("lead", "caring") and total_spent > 0:
            suggested_status = "customer"
        else:
            suggested_status = customer.status

        summary = (
            f"Khách hàng {customer.name} có {order_count} đơn hàng "
            f"và {interaction_count} tương tác. "
            f"Tổng chi tiêu: {format_vnd(total_spent)}."
        )

        actions = []
        if customer.status == "lead":
            actions.append("Gửi tài liệu giới thiệu sản phẩm")
        if customer.status == "churned":
            actions.append("Liên hệ lại để tìm hiểu nguyên nhân rời bỏ")
        if order_count == 0:
            actions.append("Tư vấn gói dịch vụ phù hợp")
        if total_spent > 5_000_000:
            actions.append("Đề xuất chương trình ưu đãi khách hàng thân thiết")
        if not actions:
            actions.append("Theo dõi và duy trì mối quan hệ")

        return {
            "sentiment": sentiment,
            "priority": priority,
            "suggested_status": suggested_status,
            "summary": summary,
            "next_actions": actions[:3],
        }

    # ------------------------------------------------ Báo cáo nhận định nhanh
    @staticmethod
    def build_report_stats():
        """Tổng hợp số liệu từ CSDL cho báo cáo (không gọi AI). Mọi giá trị đều JSON được."""
        from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum

        from crm.models import Customer, Order, OrderItem

        money = DecimalField(max_digits=18, decimal_places=0)
        now = timezone.localtime()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        def count_by(queryset, field, choices):
            counts = dict(queryset.order_by().values_list(field).annotate(n=Count("pk")))
            return {value: {"label": label, "count": counts.get(value, 0)} for value, label in choices}

        revenue = OrderItem.objects.filter(order__status=Order.Status.COMPLETED).aggregate(
            total=Sum(ExpressionWrapper(F("quantity") * F("unit_price"), output_field=money))
        )["total"]

        top_customers = (
            Customer.objects.annotate(
                spent=Sum(
                    F("orders__items__quantity") * F("orders__items__unit_price"),
                    filter=Q(orders__status=Order.Status.COMPLETED),
                    output_field=money,
                )
            )
            .filter(spent__gt=0)
            .order_by("-spent", "name")
            .values("name", "spent")[:5]
        )

        return {
            "total_customers": Customer.objects.count(),
            "new_customers_month": Customer.objects.filter(created_at__gte=month_start).count(),
            "customers_by_status": count_by(Customer.objects.all(), "status", Customer.Status.choices),
            "revenue": int(revenue or 0),
            "orders_by_status": count_by(Order.objects.all(), "status", Order.Status.choices),
            "top_customers": [{"name": c["name"], "spent": int(c["spent"])} for c in top_customers],
            "sentiment_counts": count_by(Customer.objects.all(), "ai_sentiment", Customer.Sentiment.choices),
            "analyzed_count": Customer.objects.exclude(ai_sentiment="").count(),
        }

    def generate_report(self):
        """Tạo báo cáo nhận định nhanh bằng AI dựa trên số liệu CSDL."""
        stats = self.build_report_stats()
        if self.is_mock:
            self._state.provider = "AI Gemini"
            insight = self._mock_report(stats)
        else:
            insight = self._generate_report_live(stats)
        return {
            "stats": stats,
            "insight": insight,
            "generated_at": timezone.localtime().isoformat(),
        }

    def _generate_report_live(self, stats):
        """Gọi AI thật để viết nhận định dựa trên stats."""
        stats_text = json.dumps(stats, ensure_ascii=False, indent=2)
        prompt = f"""Bạn là chuyên gia phân tích kinh doanh CRM. Dựa trên số liệu thống kê sau, hãy viết nhận định ngắn gọn bằng tiếng Việt.

SỐ LIỆU THỐNG KÊ (tiền tính bằng đồng Việt Nam):
{stats_text}

YÊU CẦU:
- Văn bản thuần: không markdown (không dùng *, #, **), không bảng, không emoji.
- Đúng 3 phần theo thứ tự, mỗi phần một dòng tiêu đề viết hoa:
  TÌNH HÌNH CHUNG / RỦI RO CẦN CHÚ Ý / ĐỀ XUẤT HÀNH ĐỘNG.
- Mỗi phần 2–4 gạch đầu dòng, mỗi dòng bắt đầu bằng "- ".
- TUYỆT ĐỐI không bịa số liệu ngoài dữ liệu đã cung cấp.
- Tổng khoảng 150–300 từ.

Chỉ trả về nội dung nhận định."""
        return self._generate(prompt)

    @staticmethod
    def _mock_report(stats):
        """Nhận định mẫu – mọi câu đều suy ra từ ``stats`` thật, không thêm thông tin ngoài."""
        churned = stats["customers_by_status"]["churned"]["count"]
        leads = stats["customers_by_status"]["lead"]["count"]
        orders = stats["orders_by_status"]
        pending = orders["new"]["count"] + orders["processing"]["count"]
        cancelled = orders["cancelled"]["count"]
        negative = stats["sentiment_counts"]["negative"]["count"]
        analyzed = stats["analyzed_count"]
        top = stats["top_customers"]
        top_text = ", ".join(f'{c["name"]} ({format_vnd(c["spent"])})' for c in top[:3]) or "chưa có"

        risks = [f"- Có {churned} khách hàng đã rời bỏ, cần tìm hiểu nguyên nhân."]
        if cancelled:
            risks.append(f"- Có {cancelled} đơn hàng bị huỷ.")
        if analyzed:
            risks.append(f"- AI ghi nhận {negative}/{analyzed} khách đã phân tích có cảm xúc tiêu cực.")
        else:
            risks.append("- Chưa có khách hàng nào được phân loại bằng AI để đánh giá cảm xúc.")

        return "\n".join([
            "TÌNH HÌNH CHUNG",
            f"- Hệ thống hiện có {stats['total_customers']} khách hàng, "
            f"trong đó {stats['new_customers_month']} khách mới trong tháng.",
            f"- Doanh thu đơn hoàn thành đạt {format_vnd(stats['revenue'])}.",
            f"- Top khách hàng chi tiêu cao: {top_text}.",
            "",
            "RỦI RO CẦN CHÚ Ý",
            *risks,
            "",
            "ĐỀ XUẤT HÀNH ĐỘNG",
            f"- Theo dõi {pending} đơn hàng mới/đang xử lý để hoàn thành đúng hạn.",
            f"- Chăm sóc {leads} khách tiềm năng để chuyển đổi thành đơn hàng.",
            "- Liên hệ lại khách hàng đã rời bỏ và duy trì ưu đãi cho nhóm chi tiêu cao.",
        ])


_service = None


def get_ai_service():
    """Trả về instance ``GeminiCRMService`` dùng chung trong toàn ứng dụng."""
    global _service
    if _service is None:
        _service = GeminiCRMService()
    return _service
