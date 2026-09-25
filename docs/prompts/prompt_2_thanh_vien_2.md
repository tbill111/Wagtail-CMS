# PROMPT 2 — THÀNH VIÊN 2: BỔ SUNG 2 TÍNH NĂNG AI

# VAI TRÒ
Bạn là một kỹ sư Python/Django cấp cao, thành thạo Wagtail CMS và Google Gemini API. Bạn nhận một dự án **đã có sẵn và đang chạy được**: **SmartCRM**, đề tài "Xây dựng hệ thống CRM thông minh tích hợp trợ lý AI Gemini trên nền tảng Wagtail CMS".
- Repo: https://github.com/tbill111/Wagtail-CMS (nhánh `main`)
- Công nghệ: Python ≥ 3.11, Wagtail 8.0, Django 6.1.1, SQLite, `google-genai` 2.25.0, `httpx`, `python-dotenv`.
- Hiện có **1 tính năng AI**: **Gợi ý email phản hồi** (chạy thật với Gemini, có MOCK, có AI dự phòng).

Nhiệm vụ: **bổ sung thêm 2 tính năng AI**, gồm (1) **Phân loại khách hàng** và (2) **Báo cáo nhận định nhanh**, tích hợp liền mạch vào code hiện có. Sau đó **kiểm tra lại toàn bộ luồng API AI** (cả tính năng cũ lẫn mới) theo mục "KIỂM TRA TOÀN BỘ LUỒNG API AI" ở cuối.

# NGUYÊN TẮC BẮT BUỘC
1. **Đọc hiểu code trước khi sửa**: đọc `README.md` (đặc biệt mục **"Hướng dẫn mở rộng tính năng AI"** và mục **6.7 AI dự phòng**), `crm/models.py`, `crm/services/ai_service.py`, `crm/views.py`, `crm/urls.py`, `crm/wagtail_hooks.py`, `crm/templates/crm/`, `crm/static/crm/`, `crm/tests/`, `crm/management/commands/seed_demo.py`, `smartcrm/settings/base.py`, `.env.example`. **Tóm tắt ngắn kiến trúc hiện tại trước khi code.**
2. **Không viết lại, không phá vỡ** tính năng/test đang có. Toàn bộ **40 test cũ** phải vẫn PASS.
3. **Tái sử dụng** những gì đã có (tên dưới đây là tên thật trong code):
   - Service: `GeminiCRMService.build_customer_context()`, `_generate(prompt, *, json_schema=None)`, `AIServiceError`, `is_mock`, `last_provider_label`, `get_ai_service()`.
   - Views: decorator `staff_required` (trang HTML), `api_staff_required` (API JSON), `json_error(message, status)`, `parse_json_body(request)`, `clean_text(...)`.
   - JS (`crm/static/crm/js/ai.js`): `postJSON(url, data)`, `setLoading(button, isLoading, text)`, `showToast(message, type)`, `escapeHTML()`; tất cả nằm trong `window.SmartCRM`.
   - CSS (`crm/static/crm/css/smartcrm.css`): `.ai-card`, `.btn-ai`, `.btn-outline-ai`, `.ai-badge`, `.ai-badge-sm`, `.text-ai`, `.sc-card`, `.sc-empty`.
   - Template tags (`crm/templatetags/crm_tags.py`): `vnd`, `status_badge`, `order_badge`, `query_string`.
4. Giữ đúng quy ước: giao diện tiếng Việt, AI dùng màu tím `#7c3aed` + ✨, Bootstrap 5, Vanilla JS, **không thêm thư viện mới** (không Chart.js, không thư viện Markdown). Không hard-code API key; **không commit `.env`**.
5. Làm trên **nhánh Git riêng** `feature/ai-classify-report` (tạo từ `main`), commit nhỏ theo từng phần, message rõ ràng (tiếng Việt hoặc tiếng Anh).
6. Nếu tên hàm/block/biến trong code khác với mô tả ở đây, **theo code thực tế** và ghi chú lại trong báo cáo.

# LƯU Ý KỸ THUẬT QUAN TRỌNG (đọc kỹ trước khi code)
Các điểm sau đã được kiểm tra trên code thật. Làm sai sẽ gây lỗi:

1. **Decorator cho API: dùng `@require_POST` + `@api_staff_required`, KHÔNG dùng `login_required`.**
   `login_required` chuyển hướng (302) sang trang đăng nhập HTML, nên `postJSON` sẽ không đọc được JSON. `api_staff_required` trả JSON 401 (chưa đăng nhập) hoặc 403 (không phải staff).
   Trang HTML dùng `@require_GET` + `@staff_required`.
2. **Link navbar "Báo cáo AI"**: đặt **trực tiếp vào nội dung mặc định** của `{% block nav_extra %}…{% endblock %}` trong `crm/base.html`.
   Không đặt link bằng cách override block trong template con, vì làm vậy link chỉ hiện trên đúng trang đó.
3. **Card "Phân loại AI" ở trang chi tiết**: `{% block ai_extra %}` nằm ngay trong `customer_detail.html` và không có template nào kế thừa trang này, nên override block sẽ không có tác dụng.
   Hãy đặt card **trực tiếp trong `<div id="ai-extra-panels">`**, nên dùng `{% include "crm/_ai_classify_card.html" %}`.
4. **Dữ liệu JSON không được chứa `Decimal`/`datetime`.** Doanh thu và `total_spent` là `Decimal`.
   `JsonResponse` tự xử lý được, nhưng **`JSONField` (ví dụ `AIReport.stats`) sẽ lỗi `TypeError: Object of type Decimal is not JSON serializable`**.
   Hãy đổi tiền sang `int` và thời gian sang chuỗi `isoformat()` trước khi lưu hoặc trả về.
5. **AI có thể không phải Gemini.** `_generate()` thử lần lượt: `GEMINI_MODEL` → `GEMINI_FALLBACK_MODEL` (khi 503) → nhà cung cấp dự phòng `FALLBACK_AI_*` (Groq/OpenRouter/DeepSeek, chuẩn OpenAI).
   Nhà cung cấp dự phòng chỉ nhận `response_format: json_object` và **không ép theo schema**, nên **bắt buộc validate kỹ** kết quả JSON.
   Mọi API AI mới phải trả thêm `provider` (lấy từ `service.last_provider_label`) để giao diện hiện đúng "Gợi ý bởi …".
6. **Chế độ MOCK**: `is_mock` = `AI_MOCK=True`, hoặc không có cả `GEMINI_API_KEY` lẫn `FALLBACK_AI_API_KEY`.
   Khi mock, mọi method AI mới phải trả kết quả giả lập **đúng cấu trúc**, và giao diện hiện nhãn **"(chế độ mô phỏng)"** như khối Gợi ý phản hồi.
7. **Test không được gọi mạng**: file `.env` trên máy có thể chứa **key thật**.
   Mọi test mới phải mock client/`httpx.post` **và** cô lập cấu hình: dùng `override_settings` giống hằng `LIVE` trong `crm/tests/test_ai_service.py` (có `FALLBACK_AI_API_KEY=""`), hoặc `AI_MOCK=True`.
8. **Model Gemini mặc định là `gemini-3.8-flash`**. `gemini-2.5-flash` không còn cấp cho API key mới (lỗi 404). Không đổi lại model cũ.
9. **Chuỗi JSON schema cho Gemini**: dùng kiểu viết hoa (`"OBJECT"`, `"STRING"`, `"ARRAY"`) và `enum` cho các giá trị cố định, giống ví dụ trong README mục mở rộng.

---

# TÍNH NĂNG 1 — PHÂN LOẠI KHÁCH HÀNG BẰNG AI

## Model (migration mới)
Thêm vào `Customer` (tạo **migration mới** bằng `makemigrations crm`, không sửa `0001_initial.py`):
- `ai_sentiment`: choices `positive` (Tích cực) / `neutral` (Trung lập) / `negative` (Tiêu cực), `blank=True`
- `ai_priority`: choices `high` (Cao) / `medium` (Trung bình) / `low` (Thấp), `blank=True`
- `ai_suggested_status`: dùng lại `Customer.Status.choices`, `blank=True`
- `ai_summary`: `TextField`, `blank=True`
- `ai_next_actions`: `JSONField(default=list, blank=True)`
- `ai_analyzed_at`: `DateTimeField(null=True, blank=True)`

Mọi trường cần có `verbose_name` tiếng Việt.

Cập nhật Wagtail Admin (`crm/wagtail_hooks.py`, class `CustomerViewSet`):
- Thêm `ai_priority`, `ai_sentiment` vào `list_display` và `list_filter`.
- Thêm `MultiFieldPanel` **"Phân tích AI"** vào `panels`. Có thể dùng `FieldPanel(..., read_only=True)`, vì Wagtail 8 hỗ trợ.

## Service
Thêm vào `GeminiCRMService`:

`analyze_customer(customer) -> dict`
- Prompt dùng `build_customer_context(customer)`. Yêu cầu AI phân tích cảm xúc qua lịch sử tương tác, mức ưu tiên chăm sóc, và trạng thái nên chuyển sang.
- Gọi `_generate(prompt, json_schema=...)` với schema:
  - `sentiment`: positive | neutral | negative
  - `priority`: high | medium | low
  - `suggested_status`: một trong các choices của status
  - `summary`: tối đa 3 câu tiếng Việt
  - `next_actions`: list tối đa 3 chuỗi
- Parse và **validate**:
  - JSON lỗi → `AIServiceError` với thông điệp tiếng Việt.
  - Giá trị ngoài danh sách → mặc định an toàn: `neutral` / `medium` / giữ nguyên status hiện tại.
  - `next_actions` không phải list → `[]`; cắt tối đa 3 phần tử; ép về chuỗi.
  - Chịu được trường hợp AI bọc JSON trong ```` ```json ```` (nhà cung cấp dự phòng hay làm vậy).
- Lưu các trường `ai_*` + `ai_analyzed_at` bằng `save(update_fields=[...])`. **Không tự đổi `status`.**
- MOCK: trả kết quả giả lập hợp lệ, suy từ số đơn/tương tác để trông hợp lý. Viết thành method riêng (ví dụ `_mock_analysis(customer)`) để `seed_demo` gọi thẳng được.

## API
| URL | Chức năng |
|---|---|
| `POST /crm/api/customers/<id>/analyze/` | Chạy phân tích → `{ok, data: {sentiment, sentiment_display, priority, priority_display, suggested_status, suggested_status_display, summary, next_actions, analyzed_at}, mock, provider}` |
| `POST /crm/api/customers/<id>/apply-status/` | Đổi `status` = `ai_suggested_status` → `{ok, status, status_display, badge_class}`. Trả 400 nếu chưa có đề xuất hoặc đề xuất trùng trạng thái hiện tại |

- Decorator: `@require_POST` + `@api_staff_required` (xem Lưu ý 1).
- Mã lỗi: 401/403 (quyền), 404 không có khách, 405 sai phương thức, 400 dữ liệu sai, 503 khi AI lỗi (`json_error(str(exc), 503)`).
- `badge_class` lấy từ filter `status_badge` trong `crm_tags.py` để JS không phải tự đoán màu.

## Giao diện
**Trang chi tiết khách**: thêm card **"✨ Phân loại AI"** (`.sc-card.ai-card`) vào `#ai-extra-panels`, phía trên khối Gợi ý phản hồi (xem Lưu ý 3).
- Chưa phân tích: dòng "Chưa có phân tích" + nút `.btn-ai` "✨ Phân tích khách hàng".
- Đã phân tích, gồm:
  - Badge cảm xúc: 😊 Tích cực / 😐 Trung lập / 😟 Tiêu cực.
  - Badge ưu tiên: Cao đỏ / Trung bình cam / Thấp xanh.
  - Tóm tắt, danh sách hành động gợi ý, thời điểm phân tích (`d/m/Y H:i`).
  - Nút "✨ Phân tích lại".
  - Nhãn "Phân tích bởi {provider}" + "(chế độ mô phỏng)" khi `mock`.
- Nếu `ai_suggested_status` khác `status`: hiện "AI đề xuất chuyển sang: **…**" + nút "Áp dụng".
  - Sau khi áp dụng, **badge trạng thái ở tiêu đề trang cập nhật ngay, không tải lại trang**.
  - Badge đó hiện chưa có `id`: hãy thêm `id="customer-status-badge"` trong `customer_detail.html`, rồi đổi class/nội dung theo `badge_class`/`status_display`.
- JS dùng `postJSON`, `setLoading(btn, true, "✨ AI đang phân tích…")`, `showToast`. Mọi nội dung AI chèn vào DOM phải qua `textContent` hoặc `escapeHTML` (không chèn HTML thô từ AI).

**Danh sách khách**: thêm cột "Ưu tiên AI" (badge; "—" nếu chưa phân tích) và bộ lọc `?priority=`.
Kiểm tra giá trị hợp lệ giống cách `status` đang làm trong `customer_list`, và giữ tham số khi phân trang (tag `query_string`).

**Tổng quan**: thêm bảng "Khách hàng ưu tiên cao (theo AI)", tối đa 5 khách, có trạng thái rỗng thân thiện.

---

# TÍNH NĂNG 2 — BÁO CÁO NHẬN ĐỊNH NHANH BẰNG AI

## Service
Thêm `generate_report() -> dict`:
- Tự tổng hợp số liệu từ CSDL bằng ORM `aggregate`/`annotate`:
  - số khách theo trạng thái, số khách mới trong tháng;
  - doanh thu đơn Hoàn thành, số đơn theo trạng thái;
  - top 5 khách chi tiêu cao;
  - tỷ lệ cảm xúc AI (nếu có).
- **Mọi số tiền đổi sang `int`** (xem Lưu ý 4).
- Gửi số liệu cho AI và yêu cầu viết nhận định **văn bản thuần tiếng Việt**, gồm 3 phần **Tình hình chung / Rủi ro cần chú ý / Đề xuất hành động**. Mỗi phần 2–4 gạch đầu dòng, không markdown, **không bịa số liệu ngoài dữ liệu đã cung cấp**.
- Trả `{"stats": {...}, "insight": "<văn bản>", "generated_at": "<isoformat>"}`. MOCK trả nhận định mẫu dựa trên stats thật.
- Tách phần tính số liệu thành hàm riêng (ví dụ `build_report_stats()`) để trang `/crm/reports/` hiển thị thẻ số mà không cần gọi AI.

## Lưu lịch sử báo cáo (khuyến khích làm)
Model **AIReport** gồm:
- `content` (TextField), `stats` (JSONField), `provider` (CharField, tên AI đã viết), `is_mock` (bool)
- FK `created_by` (User, null), `created_at`

Đăng ký Snippet trong nhóm "CRM" bằng cách thêm ViewSet vào `CRMViewSetGroup.items`, **chỉ xem**. Mỗi lần sinh báo cáo thì lưu một bản ghi, để thể hiện rõ luồng AI → CSDL → Admin.

## API & giao diện
| URL | Chức năng |
|---|---|
| `GET /crm/reports/` | Trang **"Báo cáo AI"** (`<title>Báo cáo AI \| SmartCRM</title>`), gồm: thẻ số liệu tổng hợp, nút `.btn-ai` "✨ Tạo báo cáo nhận định", khu vực kết quả `.ai-card` (`white-space: pre-line`), danh sách 5 báo cáo gần nhất (nếu có AIReport) |
| `POST /crm/api/reports/generate/` | → `{ok, stats, insight, generated_at, mock, provider}` |

- Thêm link **"Báo cáo AI"** vào navbar, đặt trong nội dung mặc định của `nav_extra` (xem Lưu ý 2). Link có trạng thái `active` khi đang ở trang báo cáo.
- Có nút "Sao chép báo cáo". Khi chờ hiện "✨ AI đang tổng hợp…".
- Khi CSDL chưa có khách: trang hiện thông báo thân thiện, nút bị ẩn hoặc khoá; API trả **400** kèm thông điệp tiếng Việt và **không gọi AI**.

---

# KIỂM THỬ TỰ ĐỘNG
Thêm test mới, **tối thiểu 8 test**. Mock mọi lời gọi AI bằng `unittest.mock` (patch `GeminiCRMService.client` hoặc method service, patch `httpx.post`), và cô lập settings theo Lưu ý 7. **Không test nào được gọi mạng.**
- `analyze_customer`:
  - prompt chứa dữ liệu khách;
  - JSON hợp lệ → lưu đúng trường `ai_*`;
  - JSON sai → `AIServiceError`; giá trị lạ → mặc định an toàn;
  - `next_actions` > 3 phần tử → cắt còn 3;
  - không tự đổi `status`;
  - MOCK hoạt động.
- API `analyze`: 200 (có `provider`), 404, 503, 405. API `apply-status`: đổi trạng thái đúng, 400 khi chưa có đề xuất.
- `generate_report`: stats tính đúng (so với dữ liệu tạo trong test); không có `Decimal` trong stats (`json.dumps(stats)` chạy được); API trả 200; tạo bản ghi AIReport; CSDL rỗng → 400 và không gọi AI.
- Trang `/crm/reports/` yêu cầu đăng nhập; navbar có link "Báo cáo AI" ở **mọi** trang `/crm/`.
- Chạy **toàn bộ** `python manage.py test crm`: 40 test cũ + test mới đều PASS.

Cập nhật `seed_demo`: thêm tuỳ chọn `--analyze` để điền sẵn dữ liệu `ai_*` cho vài khách phục vụ demo.
**Bắt buộc dùng kết quả MOCK** bằng cách gọi thẳng `_mock_analysis()` hoặc chạy trong `override_settings(AI_MOCK=True)`, **không gọi AI thật** (tránh tốn quota khi `.env` có key). Lệnh vẫn phải chạy lại nhiều lần được mà không lỗi.

---

# KIỂM TRA TOÀN BỘ LUỒNG API AI (bắt buộc, làm sau khi code xong)
Mục đích: bảo đảm **cả 3 tính năng AI** (Gợi ý phản hồi cũ, Phân loại, Báo cáo) chạy đúng từ đầu đến cuối **với AI thật**, không chỉ qua unit test. Ghi kết quả vào báo cáo, **kể cả các lần thất bại** (không được báo "đạt" nếu chưa chạy thật).

## A. Chuẩn bị
1. `python manage.py migrate` → `python manage.py seed_demo --reset --analyze` → `python manage.py runserver`.
2. Đăng nhập `/admin/` bằng tài khoản staff.
3. Mở DevTools (F12), tab **Network** + **Console**, để xem request/response JSON và lỗi JS.

## B. Ma trận chế độ AI: chạy mỗi chế độ cho **cả 3 tính năng**
Sau mỗi lần sửa `.env` phải **khởi động lại server** (`.env` chỉ được đọc lúc khởi động).

| Chế độ | Cấu hình `.env` | Kỳ vọng |
|---|---|---|
| 1. MOCK | `AI_MOCK=True` | 200, `mock: true`, giao diện hiện "(chế độ mô phỏng)", không có request ra Internet |
| 2. Gemini thật | `AI_MOCK=False`, có `GEMINI_API_KEY` | 200, `mock: false`, `provider: "AI Gemini"`, nội dung dùng đúng dữ liệu khách/số liệu thật |
| 3. AI dự phòng | Xoá `GEMINI_API_KEY`, điền `FALLBACK_AI_*` (ví dụ Groq miễn phí) | 200, `provider` = `FALLBACK_AI_NAME`; **JSON phân loại vẫn parse và validate đúng** |
| 4. Key sai | `GEMINI_API_KEY=abc`, không có dự phòng | 503, toast đỏ tiếng Việt, **không lộ key** trong toast, response hay log console |
| 5. Gemini quá tải/hết quota | Gặp tự nhiên, hoặc giả lập bằng unit test | Toast "…quá tải…" hoặc "…hết hạn mức…"; nếu có dự phòng thì tự chuyển sang dự phòng |

Nếu không có key thật cho chế độ 2 hoặc 3, ghi rõ "chưa chạy thật, lý do…" trong báo cáo.

## C. Kiểm tra từng API
Với mỗi endpoint dưới đây, xác nhận **mã HTTP + cấu trúc JSON** trong tab Network:

| Endpoint | Trường hợp phải thử |
|---|---|
| `POST /crm/api/customers/<id>/suggest-reply/` (cũ) | 200 có `reply, mock, provider`; message rỗng → 400; >2000 ký tự → 400; tone lạ → 400; id không tồn tại → 404; GET → 405 |
| `POST /crm/api/customers/<id>/save-interaction/` (cũ) | 201 có `interaction_html`; timeline cập nhật không tải lại trang; thiếu `final_reply` → 400 |
| `POST /crm/api/customers/<id>/analyze/` | 200 đủ trường `data`; badge/tóm tắt/hành động hiển thị; bấm "Phân tích lại" chạy được; 404; 503 khi AI lỗi |
| `POST /crm/api/customers/<id>/apply-status/` | Đổi trạng thái → badge tiêu đề đổi màu/chữ ngay; 400 khi chưa phân tích |
| `POST /crm/api/reports/generate/` | 200 có `stats, insight, generated_at, mock, provider`; nhận định đủ 3 phần; số liệu trong nhận định khớp thẻ số; CSDL rỗng → 400 |
| Mọi API ở trên | Chưa đăng nhập → **401 JSON** (không phải 302); user không phải staff → 403; gửi thiếu CSRF → 403 và toast "Phiên làm việc không hợp lệ" |

## D. Kiểm tra luồng dữ liệu đầy đủ (Admin → AI → Frontend → CSDL → Admin)
1. Admin: thêm khách mới, thêm 1 đơn Hoàn thành và 1–2 tương tác (có tin nhắn tiêu cực).
2. `/crm/customers/<id>/`: bấm **Phân tích khách hàng** → kiểm tra kết quả hợp lý với dữ liệu vừa nhập.
3. Bấm **Áp dụng** trạng thái đề xuất → badge cập nhật ngay.
4. Dùng **Gợi ý phản hồi** → sửa → **Lưu vào lịch sử** → bấm **Phân tích lại** (AI phải thấy tương tác mới).
5. Admin → CRM → Khách hàng: thấy cột/bộ lọc Ưu tiên AI, Cảm xúc AI; panel "Phân tích AI" có dữ liệu; trạng thái đã đổi.
6. `/crm/reports/` → tạo báo cáo → Admin → CRM → **Báo cáo AI** thấy bản ghi mới (nội dung, stats, provider).
7. `/crm/` Tổng quan: bảng "Khách hàng ưu tiên cao" có khách phù hợp.

## E. Kiểm tra phi chức năng
- Console **không có lỗi JS** ở mọi trang `/crm/`.
- Khi chờ AI, nút bị khoá; bấm liên tục không gửi nhiều request trùng.
- Giao diện mobile 375px: các card AI không tràn ngang.
- `git status` / `git diff --cached`: **không có `.env`, `db.sqlite3`, API key** trong commit.
- Chạy lại: `makemigrations --check` (không còn thay đổi), `test crm` (tất cả PASS).

---

# CẬP NHẬT TÀI LIỆU
- `README.md`:
  - thêm 2 tính năng vào mục giới thiệu;
  - cập nhật sơ đồ luồng Mermaid;
  - cập nhật **bảng Checklist 01–05 ↔ file** (mục 03, 04, 05);
  - thêm URL `/crm/reports/` và 2 API mới vào mục "Các URL chính";
  - thêm bước kiểm thử 2 tính năng mới vào mục 6.5;
  - ghi chú migration mới (`python manage.py migrate`) và `seed_demo --analyze`;
  - cập nhật số lượng test.
- `docs/TEST_CASES.md`:
  - thêm test case thủ công: phân tích khách → xem badge → áp dụng trạng thái → mở Admin thấy trường AI và trạng thái mới → tạo báo cáo AI → xem AIReport trong Admin;
  - thêm bảng kết quả **ma trận chế độ AI** (mục B) với cột "Kết quả thực tế".
- Thêm mục **"Phân công"** ngắn trong README: Nhóm trưởng phụ trách nền tảng hệ thống + Gợi ý phản hồi AI; Thành viên 2 phụ trách Phân loại khách hàng AI + Báo cáo AI.

# KIỂM TRA CUỐI
```
python manage.py makemigrations --check
python manage.py migrate
python manage.py seed_demo --reset --analyze
python manage.py test crm
python manage.py runserver   # kiểm tra /crm/, /crm/customers/<id>/, /crm/reports/, /admin/
```

# TIÊU CHÍ NGHIỆM THU
- [ ] Tính năng Gợi ý phản hồi cũ vẫn hoạt động; 40 test cũ PASS.
- [ ] Phân loại AI: phân tích, hiển thị badge/tóm tắt/hành động, áp dụng trạng thái không tải lại trang; trường AI xem/lọc được trong Admin.
- [ ] Báo cáo AI: số liệu đúng, nhận định 3 phần, có trang riêng + link navbar **ở mọi trang**; AIReport xem được trong Admin.
- [ ] Cả 2 tính năng dùng dữ liệu thật từ CSDL, có MOCK, hỗ trợ AI dự phòng, trả `provider`; lỗi AI hiển thị toast thân thiện.
- [ ] API dùng `api_staff_required` (401/403 JSON), không dùng `login_required`.
- [ ] Giao diện đồng bộ phong cách SmartCRM (tím + ✨ cho AI), responsive, không lỗi JS.
- [ ] ≥ 8 test mới PASS, không gọi mạng; README, TEST_CASES.md đã cập nhật; code nằm trên nhánh `feature/ai-classify-report`.
- [ ] Đã chạy mục **"KIỂM TRA TOÀN BỘ LUỒNG API AI"** và ghi kết quả thật (kể cả thất bại / chưa chạy được).

# ĐẦU RA
Báo cáo gồm:
- tóm tắt kiến trúc đã đọc;
- danh sách file thêm/sửa; migration mới;
- kết quả test (cũ + mới);
- **bảng kết quả kiểm tra luồng API AI** (mục B, C, D) với kết quả thực tế;
- giả định/khác biệt so với mô tả;
- hướng dẫn nhóm trưởng merge nhánh:
  ```
  git checkout main && git pull
  git merge --no-ff feature/ai-classify-report
  python manage.py migrate
  python manage.py test crm
  git push origin main
  ```
