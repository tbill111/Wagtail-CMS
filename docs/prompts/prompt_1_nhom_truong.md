# PROMPT 1 — NHÓM TRƯỞNG: XÂY DỰNG TOÀN BỘ HỆ THỐNG (1 TÍNH NĂNG AI)

# VAI TRÒ
Bạn là một kỹ sư Python/Django cấp cao, thành thạo Wagtail CMS và Google Gemini API. Nhiệm vụ: **viết hoàn chỉnh, chạy được ngay** một dự án bài tập nhóm đại học, đáp ứng **đúng và đủ 5 mục checklist**, với **đúng 1 tính năng AI: Gợi ý email phản hồi khách hàng**. Không dừng ở mức hướng dẫn — phải tạo đủ file, chạy migrate, chạy test và xác nhận hệ thống hoạt động.

**Bối cảnh chia việc:** sau khi bạn hoàn thành, một thành viên khác sẽ bổ sung thêm 2 tính năng AI (Phân loại khách hàng, Báo cáo nhận định). **Không tự làm 2 tính năng đó**, nhưng phải thiết kế code **dễ mở rộng** theo mục "ĐIỂM MỞ RỘNG" bên dưới.

# ĐỀ TÀI & THƯƠNG HIỆU
- **Tên đề tài:** Xây dựng hệ thống CRM thông minh tích hợp trợ lý AI Gemini trên nền tảng Wagtail CMS
- **Tên web:** **SmartCRM** — slogan: *"Quản lý khách hàng thông minh cùng AI"*
- Dùng tên thống nhất ở: `<title>` mọi trang (`"<Tên trang> | SmartCRM"`), navbar, trang đăng nhập, footer (`© 2026 SmartCRM – Nhóm ... – Trường Đại học Thủy Lợi`), `WAGTAIL_SITE_NAME = "SmartCRM"`, README.
- Logo: chữ "SmartCRM" + ✨ (text/SVG inline). Có favicon SVG đơn giản.

Sản phẩm **phải thể hiện luồng dữ liệu liền mạch: nhập liệu ở Wagtail Admin → AI xử lý dữ liệu đó → kết quả hiển thị ở Frontend → lưu ngược vào CSDL (xem lại được trong Admin).**

# CHECKLIST BẮT BUỘC
1. Cài đặt môi trường Python và khởi tạo dự án Wagtail CMS cơ bản.
2. Thiết kế các Model tùy chỉnh trong Wagtail để lưu trữ thông tin khách hàng, đơn hàng.
3. Tích hợp API AI để thực hiện một tính năng thông minh (gợi ý phản hồi email).
4. Xây dựng giao diện Frontend cho phép người dùng tương tác với tính năng AI.
5. Kiểm thử luồng hoạt động và đóng gói tài liệu hướng dẫn triển khai.

---

# RÀNG BUỘC KỸ THUẬT
- Python ≥ 3.11, **Wagtail bản ổn định mới nhất** (kèm Django tương thích). Ghi phiên bản cụ thể vào `requirements.txt`.
- CSDL: SQLite.
- AI SDK: **`google-genai`** (`from google import genai`). **KHÔNG dùng `google-generativeai`** (đã ngừng hỗ trợ), **KHÔNG dùng `gemini-1.5-*`** (đã bị gỡ).
- Model đọc từ env `GEMINI_MODEL`, mặc định `gemini-2.5-flash`.
- `python-dotenv` (`load_dotenv()` trong settings), **không hard-code API key**.
- **Chế độ MOCK:** `GEMINI_API_KEY` trống hoặc `AI_MOCK=True` → trả kết quả giả lập đúng cấu trúc; giao diện hiện nhãn "(chế độ mô phỏng)".
- Frontend: Django templates + **Bootstrap 5 CDN** + Vanilla JS (`fetch`). Không React/Vue, không build step, không thư viện biểu đồ.
- Giao diện, `verbose_name`, thông báo lỗi: **tiếng Việt**. Tên biến/hàm/class: tiếng Anh.
- Khởi tạo **Git repo**, commit theo từng mục (01 → 05) với message rõ ràng.

# CẤU TRÚC DỰ ÁN
```
smartcrm/
├── smartcrm/                 # settings, urls
├── home/                     # trang chủ giới thiệu SmartCRM
├── crm/
│   ├── models.py
│   ├── wagtail_hooks.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── ai_service.py
│   ├── views.py
│   ├── urls.py
│   ├── management/commands/seed_demo.py
│   ├── templates/crm/        # base.html, dashboard.html, customer_list.html, customer_detail.html, _interaction_item.html
│   ├── static/crm/           # css/smartcrm.css, js/ai.js, favicon.svg
│   └── tests/                # test_models.py, test_ai_service.py, test_views.py
├── docs/
│   ├── TEST_CASES.md
│   └── screenshots/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

# ĐẶC TẢ CHI TIẾT

## Mục 01 – Môi trường & khởi tạo
- venv → cài `wagtail`, `google-genai`, `python-dotenv` → `wagtail start smartcrm` → `pip install -r requirements.txt` → tạo app `crm`, thêm vào `INSTALLED_APPS`.
- settings: `LANGUAGE_CODE = "vi"`, `TIME_ZONE = "Asia/Ho_Chi_Minh"`, `WAGTAIL_SITE_NAME = "SmartCRM"`, `LOGIN_URL = "/admin/login/"`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `AI_MOCK` đọc từ env.
- `makemigrations`, `migrate` thành công.

## Mục 02 – Models (app `crm`)
Django model thường, đăng ký **Wagtail Snippet qua `SnippetViewSet`**, gom vào nhóm menu Admin **"CRM"** (`SnippetViewSetGroup`). Mỗi ViewSet có `list_display`, `list_filter`, `search_fields`, `panels`. Thêm menu item **"Mở SmartCRM"** trong Admin trỏ tới `/crm/`.

1. **Customer**: `name`, `email` (unique), `phone`, `company` (tuỳ chọn), `status` (`lead` Tiềm năng / `caring` Đang chăm sóc / `customer` Đã mua hàng / `churned` Đã rời bỏ), `source` (Website / Facebook / Giới thiệu / Khác), `assigned_staff` (FK User, null), `created_at`, `updated_at`; property `total_spent` (tổng đơn Hoàn thành).
   - **Không** thêm các trường `ai_*` (thành viên 2 sẽ thêm bằng migration riêng).
2. **Order** (kế thừa `ClusterableModel`): `code` tự sinh unique (`DH-YYYYMMDD-0001`), FK `customer` (`related_name="orders"`), `status` (Mới / Đang xử lý / Hoàn thành / Huỷ), `note`, `created_at`; property `total_amount`.
3. **OrderItem**: `ParentalKey` tới Order + `InlinePanel` trong form Order; `product_name`, `quantity`, `unit_price`; property `subtotal`.
4. **InteractionLog**: FK `customer` (`related_name="interactions"`), `channel` (Email / Điện thoại / Chat / Trực tiếp), `customer_message`, `ai_suggested_reply`, `final_reply`, `is_ai_generated` (bool), FK `staff` (User, null), `created_at`; `ordering = ["-created_at"]`.

## Mục 03 – Tính năng AI: Gợi ý email phản hồi
Trong `crm/services/ai_service.py`:
- `class AIServiceError(Exception)` — thông điệp tiếng Việt thân thiện.
- `class GeminiCRMService`:
  - `is_mock` (property), client khởi tạo lazy một lần.
  - `build_customer_context(customer) -> str` — **dùng chung**: thông tin khách, trạng thái, tổng chi tiêu, 5 đơn gần nhất, 5 tương tác gần nhất.
  - `_generate(prompt, *, json_schema=None) -> str` — **dùng chung**: gọi `client.models.generate_content`; nếu có `json_schema` thì dùng `response_mime_type="application/json"` + `response_schema`; bắt mọi exception → `AIServiceError`; ghi `logging`; không lộ API key.
  - `suggest_reply(customer, message, tone="lịch sự") -> str` — đóng vai nhân viên CSKH, viết email tiếng Việt ngắn gọn (chào, nội dung, kết thư), không bịa giá/chính sách ngoài dữ liệu; `tone`: lịch sự / thân thiện / trang trọng. Mock trả email mẫu có tên khách.
- Hàm `get_ai_service()` trả instance dùng chung.

## Mục 04 – Frontend (`/crm/...`)
Yêu cầu đăng nhập (`login_required`, chỉ staff). Navbar: **SmartCRM ✨** · Tổng quan · Khách hàng · Vào Admin · Đăng xuất.

| URL | Chức năng |
|---|---|
| `GET /crm/` | Tổng quan: 4 thẻ số liệu (tổng khách, khách mới trong tháng, doanh thu đơn hoàn thành, tương tác 7 ngày) + bảng 5 tương tác mới nhất |
| `GET /crm/customers/` | Danh sách: tìm theo tên/email/SĐT, lọc trạng thái, phân trang 10/trang |
| `GET /crm/customers/<id>/` | Chi tiết: thông tin, đơn hàng, timeline tương tác, khối "✨ Gợi ý phản hồi AI" |
| `POST /crm/api/customers/<id>/suggest-reply/` | vào `{message, tone}` → ra `{ok, reply, mock}` |
| `POST /crm/api/customers/<id>/save-interaction/` | lưu `InteractionLog` → trả `{ok, interaction_html}` (render `_interaction_item.html`) để chèn vào timeline |

`static/crm/js/ai.js`:
- Helper **dùng chung**: `postJSON(url, data)` (kèm `X-CSRFToken` từ cookie), `setLoading(button, isLoading, text)`, `showToast(message, type)`.
- Không tải lại trang; khi chờ: disable nút + spinner + "✨ AI đang soạn…".
- Gợi ý hiển thị trong `<textarea>` cho phép sửa, nút "Sao chép" và "Lưu vào lịch sử".
- Toast Bootstrap cho thành công/lỗi (không `window.alert`). Không gửi message rỗng; giới hạn 2000 ký tự.
- API chỉ nhận POST; 400 input sai, 404 không có khách, 503 AI lỗi.

### Giao diện (UI)
- Bootstrap 5 + font **"Be Vietnam Pro"**. CSS riêng `static/crm/css/smartcrm.css`, biến màu trên `:root`.
- Màu chính `#1e3a8a`, nền `#f5f7fb`, card trắng bo 12px, bóng nhẹ.
- **Mọi thứ liên quan AI dùng tím `#7c3aed` + ✨**; khối kết quả AI có viền trái tím và nhãn "Gợi ý bởi AI Gemini" / "(chế độ mô phỏng)". Tạo sẵn class CSS dùng chung: `.ai-card`, `.btn-ai`, `.ai-badge`.
- Badge trạng thái: Tiềm năng xám, Đang chăm sóc vàng, Đã mua hàng xanh lá, Đã rời bỏ đỏ.
- Chi tiết khách: 2 cột desktop (trái: thông tin + đơn hàng; phải: khối AI + timeline), 1 cột mobile.
- Trạng thái rỗng thân thiện ("Chưa có tương tác nào"). Responsive, tiếng Việt có dấu chuẩn.
- Trang chủ `home`: giới thiệu SmartCRM (tên, slogan, tính năng, nút "Vào hệ thống").

## ĐIỂM MỞ RỘNG (bắt buộc, để thành viên 2 làm tiếp)
- Trong `customer_detail.html`, cột phải có `{% block ai_extra %}{% endblock %}` hoặc một vùng `<div id="ai-extra-panels">` đặt **phía trên** khối Gợi ý phản hồi.
- Navbar trong `base.html` có `{% block nav_extra %}{% endblock %}` để thêm menu.
- Service tách `build_customer_context` và `_generate` như trên; không nhúng logic Gemini vào views.
- Trong README thêm mục **"Hướng dẫn mở rộng tính năng AI"** mô tả 4 bước: thêm method vào service → thêm view/URL API → thêm UI dùng `postJSON`/`.ai-card` → thêm test mock.

## Mục 05 – Kiểm thử & đóng gói
- `python manage.py seed_demo`: ~10 khách đủ trạng thái, ~12 đơn, ~20 tương tác tiếng Việt thực tế; idempotent, có `--reset`.
- Unit test (`python manage.py test crm`), **mock mọi lời gọi Gemini bằng `unittest.mock`**, tối thiểu **10 test**: sinh mã đơn, `total_amount`, `subtotal`, `total_spent`; prompt chứa dữ liệu khách; exception → `AIServiceError`; mock mode; chưa đăng nhập bị chuyển hướng; API suggest-reply 200/400/404/503; save-interaction tạo bản ghi.
- `docs/TEST_CASES.md`: bảng (Mã TC | Mô tả | Bước | Kết quả mong đợi | Kết quả thực tế) phủ luồng: thêm khách ở Admin → mở SmartCRM thấy khách → nhập tin nhắn → AI gợi ý → sửa & lưu → timeline cập nhật → mở Admin thấy InteractionLog mới.
- `README.md` (tiếng Việt): giới thiệu đề tài & SmartCRM; sơ đồ luồng dữ liệu (Mermaid); **bảng Checklist 01–05 ↔ file**; yêu cầu hệ thống; cài đặt từng bước Windows **và** macOS/Linux (clone → venv → pip → copy `.env.example` → lấy key ở Google AI Studio → migrate → createsuperuser → seed_demo → runserver); URL chính; chạy test; chế độ MOCK & xử lý sự cố (sai key, hết quota, model không tồn tại, lỗi CSRF); bảo mật (không commit `.env`); hướng dẫn mở rộng AI; mục ảnh chụp màn hình.
- `.env.example` (`GEMINI_API_KEY=`, `GEMINI_MODEL=gemini-2.5-flash`, `AI_MOCK=False`, `DJANGO_SECRET_KEY=`, `DEBUG=True`), `.gitignore` (venv, `.env`, `db.sqlite3`, `__pycache__`, `media/`).

# QUY TRÌNH & KIỂM TRA CUỐI
Làm tuần tự 01 → 05, sau mỗi mục chạy `python manage.py check`. Cuối cùng chạy và đảm bảo không lỗi:
```
python manage.py makemigrations --check
python manage.py migrate
python manage.py seed_demo
python manage.py test crm
python manage.py runserver   # /, /admin/, /crm/ trả 200 (sau đăng nhập)
```
Không có API key → kiểm thử bằng MOCK.

# TIÊU CHÍ NGHIỆM THU
- [ ] Chạy được từ đầu chỉ bằng README.
- [ ] "SmartCRM" thống nhất ở title, navbar, footer, Wagtail Admin.
- [ ] 4 model trong menu "CRM" của Admin, thêm/sửa/xoá/tìm/lọc được; Order sửa OrderItem inline.
- [ ] Gợi ý phản hồi AI dùng dữ liệu thật từ CSDL, AJAX không tải lại trang, lưu ngược vào CSDL, xem được trong Admin; có MOCK.
- [ ] Phần AI phân biệt bằng tím + ✨; responsive.
- [ ] Có đủ các điểm mở rộng cho thành viên 2.
- [ ] Không có API key trong code; dùng `google-genai`.
- [ ] ≥ 10 unit test PASS, không gọi mạng.
- [ ] Đủ README, TEST_CASES.md, `.env.example`, `.gitignore`, `requirements.txt`; Git có commit theo từng mục.

# ĐẦU RA
Báo cáo: cây thư mục; bảng Checklist 01–05 ✅ + file; kết quả test; giả định/hạn chế.
