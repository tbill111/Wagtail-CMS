# Kịch bản kiểm thử – SmartCRM

Phạm vi: luồng dữ liệu **Wagtail Admin → AI Gemini → Frontend → lưu ngược CSDL → xem lại trong Admin**
cho tính năng **Gợi ý email phản hồi khách hàng**.

Môi trường: Windows 11, Python 3.13, Wagtail 8.0, Django 6.1.1, SQLite, trình duyệt Chrome/Edge.
Dữ liệu: `python manage.py seed_demo --reset`, tài khoản quản trị tạo bằng `createsuperuser`.
Chế độ AI: chạy ở **chế độ mô phỏng** (không có `GEMINI_API_KEY`). Khi có key thật, lặp lại TC-06 → TC-09 với Gemini.

## 1. Kiểm thử thủ công (end-to-end)

| Mã TC | Mô tả | Bước | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|---|
| TC-01 | Chưa đăng nhập bị chặn | Mở `http://127.0.0.1:8000/crm/` khi chưa đăng nhập | Chuyển tới `/admin/login/?next=/crm/` | Đạt |
| TC-02 | Đăng nhập & vào SmartCRM | Đăng nhập ở `/admin/` → menu trái bấm **Mở SmartCRM** | Mở trang Tổng quan với 4 thẻ số liệu và bảng 5 tương tác mới nhất | Đạt |
| TC-03 | Thêm khách hàng ở Admin | Admin → **CRM → Khách hàng → Thêm**: Tên "Nguyễn Thị Kiểm Thử", email `kiemthu@example.com`, trạng thái "Đang chăm sóc" → Lưu | Thông báo lưu thành công, khách xuất hiện trong danh sách Admin | Đạt |
| TC-04 | Thêm đơn hàng có nhiều dòng | Admin → **CRM → Đơn hàng → Thêm**: chọn khách vừa tạo, trạng thái "Hoàn thành", thêm 2 dòng sản phẩm (inline) → Lưu | Đơn có mã dạng `DH-YYYYMMDD-000N`, cột tổng tiền đúng | Đạt |
| TC-05 | Khách hiển thị ở Frontend | Mở `/crm/customers/`, tìm "Kiểm Thử" → **Chi tiết** | Thấy thông tin khách, badge vàng "Đang chăm sóc", đơn hàng vừa tạo, tổng chi tiêu đúng, timeline hiển thị "Chưa có tương tác nào" | Đạt |
| TC-06 | Chặn tin nhắn rỗng | Để trống ô tin nhắn → bấm **✨ Gợi ý phản hồi** | Toast cảnh báo "Vui lòng nhập tin nhắn…", không gửi request | Đạt |
| TC-07 | AI gợi ý phản hồi | Nhập "Đơn hàng của tôi bao giờ được giao?", chọn giọng "Trang trọng" → **✨ Gợi ý phản hồi** | Nút bị khoá + spinner "✨ AI đang soạn…"; sau đó khung kết quả viền tím hiện email có tên khách, nhãn "Gợi ý bởi AI Gemini (chế độ mô phỏng)"; trang **không tải lại** | Đạt |
| TC-08 | Sao chép gợi ý | Bấm **📋 Sao chép** | Toast "Đã sao chép…", dán ra được nội dung | Đạt |
| TC-09 | Sửa & lưu vào lịch sử | Sửa vài chữ trong ô phản hồi → **💾 Lưu vào lịch sử** | Toast thành công; mục mới xuất hiện đầu timeline với badge "✨ AI hỗ trợ" và nội dung đã sửa; ô nhập được làm trống | Đạt |
| TC-10 | Xem lại trong Admin | Admin → **CRM → Lịch sử tương tác** → mở bản ghi mới nhất | Có đủ: khách, kênh, tin nhắn khách, gợi ý AI gốc, phản hồi đã sửa, "Có dùng AI" = Có, nhân viên xử lý | Đạt |
| TC-11 | Tổng quan cập nhật | Quay lại `/crm/` | "Tương tác 7 ngày qua" tăng 1, tương tác mới ở đầu bảng | Đạt |
| TC-12 | Tìm kiếm / lọc / phân trang | `/crm/customers/` lọc "Đã rời bỏ"; tìm theo SĐT `0901234567`; thêm >10 khách để xem phân trang | Kết quả đúng bộ lọc, phân trang 10/trang, giữ tham số lọc khi chuyển trang | Đạt |
| TC-13 | AI lỗi (key sai) | Đặt `GEMINI_API_KEY=abc`, `AI_MOCK=False`, khởi động lại → gợi ý phản hồi | Toast đỏ tiếng Việt "API key Gemini không hợp lệ…", API trả 503, không lộ key | Đạt (kiểm bằng unit test giả lập lỗi) |
| TC-14 | Responsive | Mở trang chi tiết ở độ rộng 375px (DevTools) | Bố cục 1 cột, khối AI nằm trên timeline, không tràn ngang | Đạt |
| TC-15 | AI dự phòng | Điền `FALLBACK_AI_*` (ví dụ Groq), xoá `GEMINI_API_KEY`, khởi động lại → gợi ý phản hồi | Email được soạn, nhãn "Gợi ý bởi Groq Llama 3.3" | Chưa chạy với key thật (chưa có key Groq); đã kiểm bằng unit test |
| TC-16 | Phân loại KH AI | Mở chi tiết KH chưa phân tích → bấm **✨ Phân tích khách hàng** | Nút đổi trạng thái "Đang phân tích...", sau đó hiện kết quả: badge cảm xúc, badge ưu tiên, gợi ý chuyển trạng thái (nếu có), phần nhận định và hành động, cập nhật thời gian | Đạt |
| TC-17 | Áp dụng trạng thái đề xuất | KH có trạng thái đề xuất khác hiện tại → bấm **Áp dụng** | Trạng thái ở cột trái lập tức cập nhật màu sắc và chữ, không tải lại trang, nút áp dụng ẩn đi | Đạt |
| TC-18 | Danh sách và lọc ưu tiên | Mở `/crm/customers/`, chọn bộ lọc "Ưu tiên AI" = "Cao" | Bảng hiện cột Ưu tiên AI có badge màu, chỉ hiển thị danh sách khách có ưu tiên cao | Đạt |
| TC-19 | Xem khách ưu tiên trên Dashboard | Mở `/crm/` | Dashboard hiển thị bảng "✨ Khách hàng ưu tiên cao (theo AI)" (tối đa 5 khách) phía trên bảng "5 tương tác mới nhất" | Đạt |
| TC-20 | Báo cáo AI | Mở `/crm/reports/` → bấm **✨ Tạo báo cáo nhận định** | Các thẻ số liệu hiển thị đúng; sinh ra phần text báo cáo dạng văn bản thuần hiển thị đẹp, nút "Sao chép" xuất hiện | Đạt |
| TC-21 | Xem lại báo cáo trong Admin | Admin → **CRM → Báo cáo AI** | Báo cáo vừa tạo hiển thị read-only, đúng thông tin provider, is_mock, ngày tạo và người tạo | Đạt |

## 2. Ma trận kiểm tra các chế độ AI (cả 3 tính năng)

Chạy ngày 27/09/2026 trên bản sao CSDL sau `seed_demo --reset --analyze`, gọi API qua Django test client (có đăng nhập staff).
"Chưa chạy thật" nghĩa là chỉ có unit test giả lập, chưa gọi dịch vụ thật.

| Chế độ | Cấu hình `.env` | Kỳ vọng | Kết quả thực tế |
|---|---|---|---|
| **1. MOCK** | `AI_MOCK=True` | 200, `mock: true`, giao diện hiện "(chế độ mô phỏng)", không gọi Internet | **Đạt** – cả 3 API trả 200, `mock: true`; phân tích 11 khách, `can_apply` chỉ `true` khi đề xuất khác trạng thái; báo cáo lưu `AIReport` |
| **2. Gemini thật** | `AI_MOCK=False`, có `GEMINI_API_KEY` | 200, `mock: false`, `provider: "AI Gemini"`, nội dung dùng đúng dữ liệu | **Đạt** – Gợi ý phản hồi 200 (email có tên khách); Báo cáo 200, đủ 3 phần, số liệu khớp thẻ số (11 khách, 44.160.000 ₫); Phân loại: lần 1 **503** "Máy chủ Gemini đang quá tải…" (cả `gemini-3.8-flash` lẫn model dự phòng đều quá tải), lần 2 **200** qua model dự phòng, JSON hợp lệ, đề xuất đúng "Đã rời bỏ" cho khách đã chuyển sang phần mềm khác |
| **3. AI dự phòng** | Xoá `GEMINI_API_KEY`, điền `FALLBACK_AI_*` (Groq/OpenRouter) | 200, `provider` = `FALLBACK_AI_NAME`; JSON phân loại vẫn parse/validate đúng | **Chưa chạy thật** – máy kiểm thử chưa có key Groq/OpenRouter. Unit test `test_fallback_provider_json_is_parsed_and_labelled` giả lập nhà cung cấp trả JSON bọc ```` ```json ```` → parse đúng, `ai_provider` = tên dự phòng |
| **4. Key sai** | `GEMINI_API_KEY=abc`, không có dự phòng | 503, toast đỏ tiếng Việt, không lộ key | **Đạt** – cả 3 API trả 503 "API key Gemini không hợp lệ hoặc chưa được cấp quyền…", response và log không chứa key |
| **5. Gemini quá tải / hết quota** | Gặp tự nhiên hoặc giả lập | Toast "…quá tải…"/"…hết hạn mức…"; có dự phòng thì tự chuyển | **Đạt (gặp tự nhiên)** – xem chế độ 2: model chính quá tải → tự thử `GEMINI_FALLBACK_MODEL`; khi cả hai lỗi trả 503 thông điệp tiếng Việt. Hết quota (429) và chuyển sang AI dự phòng: chỉ kiểm bằng unit test |

## 3. Kiểm thử tự động

Chạy: `python manage.py test crm` — mọi lời gọi AI đều được giả lập bằng `unittest.mock` và cấu hình được cô lập bằng `override_settings`, **không gọi mạng** dù `.env` có key thật.

| Nhóm | File | Nội dung chính |
|---|---|---|
| Model | `crm/tests/test_models.py` | Sinh mã đơn `DH-YYYYMMDD-0001` và tăng dần; `subtotal`; `total_amount`; `total_spent` chỉ tính đơn Hoàn thành; thứ tự tương tác |
| AI service | `crm/tests/test_ai_service.py` | Prompt chứa dữ liệu khách/đơn/tin nhắn/giọng văn; model quá tải (503) tự chuyển sang model dự phòng; Gemini lỗi thì chuyển sang AI dự phòng tương thích OpenAI (Groq/OpenRouter/DeepSeek), xử lý lỗi 402/mạng, bỏ thẻ `<think>`; exception SDK → `AIServiceError` (không lộ key); phản hồi rỗng; `json_schema` → `application/json`; client lazy; chế độ MOCK. **Phân loại**: prompt chứa dữ liệu khách + dùng schema; JSON hợp lệ → lưu đủ trường `ai_*`, không đổi `status`; JSON sai → `AIServiceError`; giá trị lạ/sai kiểu → mặc định an toàn; cắt 3 hành động; JSON bọc ```` ``` ```` hoặc có lời dẫn; AI dự phòng; MOCK không gọi AI. **Báo cáo**: số khách/đơn theo trạng thái, doanh thu, top khách, cảm xúc khớp dữ liệu; `json.dumps(stats)` chạy được; prompt chứa số liệu; nhận định MOCK chỉ dùng số liệu thật |
| Views/API | `crm/tests/test_views.py` | Chưa đăng nhập → chuyển hướng; user không phải staff bị chặn; API suggest-reply 200/400/404/405/503; save-interaction; tìm kiếm/lọc/phân trang. **API mới**: analyze 200 (có `provider`, `can_apply`, giờ Việt Nam)/404/405/503; apply-status đổi trạng thái + `badge_class`, 400 khi chưa có hoặc trùng đề xuất; 401/403 JSON cho cả 3 API mới; generate-report 200 + lưu `AIReport`, 503, CSDL rỗng → 400 và không gọi AI; `/crm/reports/` yêu cầu đăng nhập; navbar có link "Báo cáo AI" ở mọi trang `/crm/`; Admin "Báo cáo AI" chỉ xem; `seed_demo --analyze` không gọi AI và chạy lại được |

Kết quả lần chạy gần nhất: **65 test – OK** (40 test cũ + 25 test mới).

## 4. Kiểm thử E2E trên trình duyệt (Phân loại AI + Báo cáo AI)

Chạy ngày 27/09/2026 bằng Playwright điều khiển Google Chrome thật (chế độ MOCK, dữ liệu `seed_demo --reset --analyze` + 1 khách mới chưa phân tích). Kịch bản bấm đúng như người dùng; ảnh chụp lưu ở `docs/screenshots/12-…19-…`. Xác nhận TC-16 → TC-21 ở mục 1.

| Bước | Kiểm tra | Kết quả |
|---|---|---|
| Đăng nhập → `/crm/` | Bảng "✨ Khách hàng ưu tiên cao (theo AI)" có dữ liệu; navbar có link "Báo cáo AI" | Đạt |
| `/crm/customers/` → chọn Ưu tiên AI = Cao → **Lọc** | URL có `?priority=high`, mọi dòng đều badge đỏ "Cao" | Đạt |
| Khách chưa phân tích | Card hiện "Chưa có phân tích" | Đạt |
| Bấm đúp **✨ Phân tích khách hàng** | Chỉ 1 request `analyze` được gửi; hiện badge cảm xúc/ưu tiên, tóm tắt, hành động, "Phân tích bởi AI Gemini (chế độ mô phỏng)"; nút đổi thành "✨ Phân tích lại" | Đạt |
| Khách Tiềm năng có đề xuất → **Áp dụng** | Badge tiêu đề đổi "Tiềm năng" → "Đang chăm sóc" (màu vàng) **không tải lại trang**; khối đề xuất ẩn | Đạt |
| Bấm **Phân tích lại** sau khi áp dụng | Nút "Áp dụng" chỉ hiện khi đề xuất khác trạng thái hiện tại | Đạt |
| Navbar → **Báo cáo AI** | Link active; title "Báo cáo AI \| SmartCRM" | Đạt |
| **✨ Tạo báo cáo nhận định** | Đủ 3 phần; doanh thu trong nhận định khớp thẻ số; nút "Sao chép báo cáo" hiện; bảng "5 báo cáo gần nhất" thêm dòng mới | Đạt |
| Admin → sửa khách | Có panel "Phân tích AI" (chỉ đọc) với dữ liệu mới | Đạt |
| Admin → CRM → Khách hàng | Có cột "Ưu tiên AI", lọc được | Đạt |
| Admin → CRM → Báo cáo AI | Có bản ghi vừa tạo, **không có nút Thêm**, mở xem chi tiết được | Đạt |
| Mobile 375px: `/crm/`, chi tiết khách, `/crm/reports/` | Không tràn ngang | Đạt |
| Toàn bộ kịch bản | Không có lỗi JavaScript/console | Đạt |

**Tổng: 26/26 kiểm tra PASS.**

Triển khai Docker (README mục 9) cũng đã chạy thử: `docker build` → `docker run --env-file` → `createsuperuser` + `seed_demo --analyze` trong container → đăng nhập, Phân tích khách và Tạo báo cáo trên trình duyệt: Đạt, không lỗi JS, file tĩnh (CSS/JS) tải được.
