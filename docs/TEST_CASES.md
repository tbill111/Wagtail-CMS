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

## 2. Kiểm thử tự động

Chạy: `python manage.py test crm` — mọi lời gọi Gemini đều được giả lập bằng `unittest.mock`, **không gọi mạng**.

| Nhóm | File | Nội dung chính |
|---|---|---|
| Model | `crm/tests/test_models.py` | Sinh mã đơn `DH-YYYYMMDD-0001` và tăng dần; `subtotal`; `total_amount`; `total_spent` chỉ tính đơn Hoàn thành; thứ tự tương tác |
| AI service | `crm/tests/test_ai_service.py` | Prompt chứa dữ liệu khách/đơn/tin nhắn/giọng văn; model quá tải (503) tự chuyển sang model dự phòng; Gemini lỗi thì chuyển sang AI dự phòng tương thích OpenAI (Groq/OpenRouter/DeepSeek), xử lý lỗi 402/mạng, bỏ thẻ `<think>`; exception SDK → `AIServiceError` (không lộ key); phản hồi rỗng; `json_schema` → `application/json`; client lazy; chế độ MOCK |
| Views/API | `crm/tests/test_views.py` | Chưa đăng nhập → chuyển hướng; user không phải staff bị chặn; API suggest-reply 200/400/404/405/503; mock end-to-end; save-interaction tạo bản ghi + trả HTML; tìm kiếm/lọc/phân trang |

Kết quả lần chạy gần nhất: **40 test – OK** (xem README mục "Chạy kiểm thử").
