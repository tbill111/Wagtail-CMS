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
    _VALID_SENTIMENTS = {"positive", "neutral", "negative"}
    _VALID_PRIORITIES = {"high", "medium", "low"}

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

    def analyze_customer(self, customer):
        """Phân loại khách hàng bằng AI: cảm xúc, mức ưu tiên, trạng thái đề xuất, tóm tắt, hành động."""
        if self.is_mock:
            self._state.provider = "AI Gemini"
            result = self._mock_analysis(customer)
        else:
            result = self._analyze_customer_live(customer)

        # Lưu vào CSDL
        customer.ai_sentiment = result["sentiment"]
        customer.ai_priority = result["priority"]
        customer.ai_suggested_status = result["suggested_status"]
        customer.ai_summary = result["summary"]
        customer.ai_next_actions = result["next_actions"]
        customer.ai_analyzed_at = timezone.now()
        customer.save(
            update_fields=[
                "ai_sentiment", "ai_priority", "ai_suggested_status",
                "ai_summary", "ai_next_actions", "ai_analyzed_at",
            ]
        )
        return result

    def _analyze_customer_live(self, customer):
        """Gọi AI thật để phân tích khách hàng, validate kết quả."""
        from crm.models import Customer

        valid_statuses = set(Customer.Status.values)

        prompt = f"""Bạn là chuyên gia phân tích CRM. Hãy phân tích khách hàng sau và trả về JSON:

{self.build_customer_context(customer)}

YÊU CẦU:
1. sentiment: đánh giá cảm xúc qua lịch sử tương tác (positive / neutral / negative)
2. priority: mức ưu tiên chăm sóc (high / medium / low)
3. suggested_status: trạng thái nên chuyển sang (lead / caring / customer / churned)
4. summary: tóm tắt ngắn gọn tối đa 3 câu bằng tiếng Việt
5. next_actions: danh sách tối đa 3 hành động cụ thể nên làm, bằng tiếng Việt

Chỉ dùng thông tin trong dữ liệu. KHÔNG bịa thêm.
Trả về đúng một JSON object."""

        text = self._generate(prompt, json_schema=self._CLASSIFY_SCHEMA)
        data = self._parse_json_safe(text)

        # Validate và áp dụng giá trị mặc định an toàn
        sentiment = data.get("sentiment", "neutral")
        if sentiment not in self._VALID_SENTIMENTS:
            sentiment = "neutral"

        priority = data.get("priority", "medium")
        if priority not in self._VALID_PRIORITIES:
            priority = "medium"

        suggested_status = data.get("suggested_status", customer.status)
        if suggested_status not in valid_statuses:
            suggested_status = customer.status

        summary = str(data.get("summary", ""))[:500]

        next_actions = data.get("next_actions", [])
        if not isinstance(next_actions, list):
            next_actions = []
        next_actions = [str(a) for a in next_actions[:3]]

        return {
            "sentiment": sentiment,
            "priority": priority,
            "suggested_status": suggested_status,
            "summary": summary,
            "next_actions": next_actions,
        }

    @staticmethod
    def _parse_json_safe(text):
        """Parse JSON từ AI, chịu được bọc ```json ... ```."""
        text = text.strip()
        # Loại bỏ markdown code fence
        match = re.match(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AIServiceError(
                "AI trả về dữ liệu không đúng định dạng JSON. Vui lòng thử lại."
            ) from exc
        if not isinstance(data, dict):
            raise AIServiceError("AI trả về dữ liệu không đúng cấu trúc. Vui lòng thử lại.")
        return data

    @staticmethod
    def _mock_analysis(customer):
        """Trả kết quả phân tích giả lập hợp lý dựa trên dữ liệu khách."""
        order_count = customer.orders.count()
        interaction_count = customer.interactions.count()
        total_spent = int(customer.total_spent)

        # Suy sentiment từ trạng thái
        if customer.status == "churned":
            sentiment = "negative"
        elif total_spent > 5000000:
            sentiment = "positive"
        elif interaction_count > 2:
            sentiment = "positive"
        else:
            sentiment = "neutral"

        # Suy priority
        if total_spent > 10000000 or customer.status == "churned":
            priority = "high"
        elif order_count >= 2:
            priority = "medium"
        else:
            priority = "low"

        # Đề xuất trạng thái
        if customer.status == "lead" and interaction_count >= 2:
            suggested_status = "caring"
        elif customer.status == "caring" and order_count >= 1:
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
        if total_spent > 5000000:
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
        """Tổng hợp số liệu từ CSDL để đưa vào báo cáo (không gọi AI)."""
        from crm.models import Customer, Order, OrderItem

        now = timezone.localtime()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Số khách theo trạng thái
        customers_by_status = {}
        for status_val, status_label in Customer.Status.choices:
            customers_by_status[status_val] = {
                "label": status_label,
                "count": Customer.objects.filter(status=status_val).count(),
            }
        total_customers = Customer.objects.count()
        new_customers_month = Customer.objects.filter(created_at__gte=month_start).count()

        # Doanh thu đơn hoàn thành
        from django.db.models import DecimalField as DF
        from django.db.models import ExpressionWrapper as EW
        from django.db.models import F as Fld
        from django.db.models import Sum as Sm

        revenue = OrderItem.objects.filter(
            order__status=Order.Status.COMPLETED
        ).aggregate(
            total=Sm(
                EW(Fld("quantity") * Fld("unit_price"), output_field=DF(max_digits=18, decimal_places=0))
            )
        )["total"]
        revenue = int(revenue or 0)

        # Số đơn theo trạng thái
        orders_by_status = {}
        for status_val, status_label in Order.Status.choices:
            orders_by_status[status_val] = {
                "label": status_label,
                "count": Order.objects.filter(status=status_val).count(),
            }

        # Top 5 khách chi tiêu cao
        top_customers = []
        for c in Customer.objects.all():
            spent = int(c.total_spent)
            if spent > 0:
                top_customers.append({"name": c.name, "spent": spent})
        top_customers.sort(key=lambda x: x["spent"], reverse=True)
        top_customers = top_customers[:5]

        # Tỷ lệ cảm xúc AI
        sentiment_counts = {}
        for s_val, s_label in Customer.Sentiment.choices:
            sentiment_counts[s_val] = {
                "label": s_label,
                "count": Customer.objects.filter(ai_sentiment=s_val).count(),
            }
        analyzed_count = Customer.objects.exclude(ai_sentiment="").count()

        return {
            "total_customers": total_customers,
            "new_customers_month": new_customers_month,
            "customers_by_status": customers_by_status,
            "revenue": revenue,
            "orders_by_status": orders_by_status,
            "top_customers": top_customers,
            "sentiment_counts": sentiment_counts,
            "analyzed_count": analyzed_count,
        }

    def generate_report(self):
        """Tạo báo cáo nhận định nhanh bằng AI dựa trên số liệu CSDL."""
        stats = self.build_report_stats()
        generated_at = timezone.now().isoformat()

        if self.is_mock:
            self._state.provider = "AI Gemini"
            insight = self._mock_report(stats)
        else:
            insight = self._generate_report_live(stats)

        return {
            "stats": stats,
            "insight": insight,
            "generated_at": generated_at,
        }

    def _generate_report_live(self, stats):
        """Gọi AI thật để viết nhận định dựa trên stats."""
        stats_text = json.dumps(stats, ensure_ascii=False, indent=2)
        prompt = f"""Bạn là chuyên gia phân tích kinh doanh CRM. Dựa trên số liệu thống kê sau, hãy viết nhận định ngắn gọn bằng tiếng Việt.

SỐ LIỆU THỐNG KÊ:
{stats_text}

YÊU CẦU:
- Viết nhận định văn bản thuần (không markdown, không bảng, không emoji).
- Gồm 3 phần: Tình hình chung / Rủi ro cần chú ý / Đề xuất hành động.
- Mỗi phần có tiêu đề rồi 2–4 gạch đầu dòng.
- TUYỆT ĐỐI không bịa số liệu ngoài dữ liệu đã cung cấp.
- Tổng khoảng 150–300 từ.

Chỉ trả về nội dung nhận định."""

        return self._generate(prompt)

    @staticmethod
    def _mock_report(stats):
        """Trả nhận định mẫu dựa trên stats thật."""
        total = stats["total_customers"]
        revenue = stats["revenue"]
        new_month = stats["new_customers_month"]
        churned = stats["customers_by_status"].get("churned", {}).get("count", 0)
        top = stats["top_customers"]
        top_text = (
            ", ".join(f'{c["name"]} ({format_vnd(c["spent"])})' for c in top[:3])
            if top
            else "chưa có"
        )

        return (
            "TÌNH HÌNH CHUNG\n"
            f"- Hệ thống hiện có {total} khách hàng, trong đó {new_month} khách mới trong tháng.\n"
            f"- Doanh thu đơn hoàn thành đạt {format_vnd(revenue)}.\n"
            f"- Top khách hàng chi tiêu cao: {top_text}.\n"
            "\n"
            "RỦI RO CẦN CHÚ Ý\n"
            f"- Có {churned} khách hàng đã rời bỏ, cần tìm hiểu nguyên nhân.\n"
            "- Một số tương tác của khách chưa được phản hồi.\n"
            "\n"
            "ĐỀ XUẤT HÀNH ĐỘNG\n"
            "- Ưu tiên phản hồi các tin nhắn chưa được trả lời.\n"
            "- Liên hệ lại khách hàng đã rời bỏ để giữ chân.\n"
            "- Xây dựng chương trình ưu đãi cho khách hàng chi tiêu cao.\n"
        )


_service = None


def get_ai_service():
    """Trả về instance ``GeminiCRMService`` dùng chung trong toàn ứng dụng."""
    global _service
    if _service is None:
        _service = GeminiCRMService()
    return _service
