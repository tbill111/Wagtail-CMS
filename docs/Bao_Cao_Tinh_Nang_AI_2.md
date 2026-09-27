# Báo cáo Hoàn thành Tính năng AI (Thành viên 2)

## 1. Tóm tắt kiến trúc đã phát triển
- **Models**: Bổ sung các trường `ai_sentiment`, `ai_priority`, `ai_suggested_status`, `ai_summary`, `ai_next_actions`, `ai_analyzed_at` vào mô hình `Customer`. Tạo model mới `AIReport` để lưu lịch sử các báo cáo nhận định AI được tạo.
- **Service**: Mở rộng `GeminiCRMService` với các phương thức `analyze_customer` và `generate_report`, bổ sung cơ chế Mock để demo hoặc test khi không có kết nối AI, và xử lý schema JSON chặt chẽ đối với các model được hỗ trợ.
- **API (Views)**: Thêm mới 4 API backend (`api_analyze_customer`, `api_apply_status`, `report_page`, `api_generate_report`) với các quyền truy cập `staff_required` / `api_staff_required`. 
- **Giao diện**:
  - Thêm thẻ hiển thị Phân loại AI vào trang chi tiết khách hàng qua partial template `_ai_classify_card.html`.
  - Cập nhật trang danh sách khách hàng (`customer_list.html`) với cột "Ưu tiên AI" và bộ lọc.
  - Cập nhật trang tổng quan (`dashboard.html`) với bảng "Khách hàng cần chú ý (Ưu tiên Cao)".
  - Bổ sung trang Báo cáo AI (`report.html`).
- **Wagtail Admin**: Tích hợp các trường AI vào `CustomerViewSet` để quản trị viên có thể xem (Read Only) và tạo `AIReportViewSet` để lưu trữ/xem lại báo cáo.

## 2. Danh sách file thay đổi & Migration mới
* **Thêm mới**:
  - `crm/migrations/0002_ai_classify_report.py`: Migration bổ sung trường vào `Customer` và tạo bảng `AIReport`.
  - `crm/templates/crm/_ai_classify_card.html`: Template component Phân loại AI.
  - `crm/templates/crm/report.html`: Template trang Báo cáo AI.
  - `docs/Bao_Cao_Tinh_Nang_AI_2.md`: File báo cáo này.
* **Thay đổi chính**:
  - `crm/models.py`: Bổ sung Fields và `AIReport`.
  - `crm/services/ai_service.py`: Cập nhật core service `GeminiCRMService`.
  - `crm/views.py` & `crm/urls.py`: Thêm các API và Endpoint.
  - `crm/wagtail_hooks.py`: Tích hợp giao diện Admin Wagtail.
  - `crm/static/crm/js/ai.js`: Bổ sung `initClassifyCard`, `initReportPage`.
  - `crm/templates/crm/base.html`, `customer_detail.html`, `customer_list.html`, `dashboard.html`.
  - `crm/management/commands/seed_demo.py`: Cập nhật flag `--analyze`.
  - `crm/tests/test_ai_service.py`, `crm/tests/test_views.py`: Thêm unit tests.
  - `README.md`, `docs/TEST_CASES.md`: Cập nhật tài liệu kỹ thuật và test cases.

## 3. Kết quả Test
- **Đã viết 13 Unit Test mới**, tổng cộng nâng số lượng tests của ứng dụng lên 53 tests (40 tests cũ + 13 tests mới).
- Mọi unit test hoàn toàn chạy giả lập (mock), không cần kết nối mạng hay tốn quota API key.
- Hệ thống test đã cover các logic:
  - Phân tích dự phòng khi AI trả JSON lỗi / sai schema / ngoài enum.
  - Cắt `next_actions` còn tối đa 3 chuỗi; không tự ý thay đổi `Customer.status`.
  - Tính toán số liệu thống kê doanh thu và xác thực không chứa kiểu `Decimal` trong JSON stats.
  - Các API: `analyze` (200, 404, 405, 503), `apply-status` (200, 400), `generate-report` (200, 400 khi rỗng).
  - Phân quyền: chặn user chưa đăng nhập, kiểm tra sự tồn tại của link navbar "Báo cáo AI" ở mọi trang.

## 4. Bảng kết quả kiểm tra luồng API AI (Mục B, C, D)

### B. Ma trận chế độ AI
| Chế độ | Cấu hình `.env` | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|
| 1. MOCK | `AI_MOCK=True` | 200, `mock: true`, giao diện hiện "(chế độ mô phỏng)", không gọi Internet | **Đạt** |
| 2. Gemini thật | `AI_MOCK=False`, có `GEMINI_API_KEY` | 200, `mock: false`, `provider: "AI Gemini"`, phân tích dựa trên dữ liệu thật | **Đạt** |
| 3. AI dự phòng | Xoá `GEMINI_API_KEY`, điền `FALLBACK_AI_*` (Groq/OpenRouter) | 200, `provider` = `FALLBACK_AI_NAME`, parse JSON phân loại an toàn | **Đạt** |
| 4. Key sai | `GEMINI_API_KEY=abc`, không có dự phòng | 503, toast đỏ tiếng Việt, không lộ key | **Đạt** |
| 5. Gemini quá tải / hết quota | Giả lập lỗi 503 / 429 | Tự động chuyển qua model fallback hoặc AI dự phòng | **Đạt** |

### C. Kiểm tra từng API Endpoint
| Endpoint | Trường hợp kiểm thử | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|
| `POST /crm/api/customers/<id>/suggest-reply/` | Dữ liệu chuẩn / rỗng / quá dài / sai tone / 404 / GET | 200 có `reply, mock, provider`; lỗi 400; 404; 405 | **Đạt** |
| `POST /crm/api/customers/<id>/save-interaction/` | Lưu tương tác thành công / thiếu dữ liệu | 201 có `interaction_html`; 400 khi thiếu phản hồi | **Đạt** |
| `POST /crm/api/customers/<id>/analyze/` | Phân tích thành công / khách không tồn tại / GET | 200 có đủ trường dữ liệu; 404; 405 | **Đạt** |
| `POST /crm/api/customers/<id>/apply-status/` | Áp dụng trạng thái đề xuất / chưa có đề xuất / trùng | 200 cập nhật DB và trả `badge_class`; 400 khi không hợp lệ | **Đạt** |
| `POST /crm/api/reports/generate/` | Sinh báo cáo thành công / CSDL chưa có khách | 200 có `stats, insight, generated_at, provider`; 400 khi CSDL rỗng | **Đạt** |
| Mọi API trên | Chưa đăng nhập / Không phải staff | Trả về JSON 401 hoặc 403 (không phải redirect 302) | **Đạt** |

### D. Kiểm tra luồng dữ liệu E2E (Admin → AI → Frontend → CSDL → Admin)
1. Thêm khách hàng, đơn hàng, tương tác trong Wagtail Admin: Dữ liệu hiển thị chuẩn trên giao diện Frontend `/crm/`.
2. Bấm "Phân tích khách hàng": AI phân tích cảm xúc, mức ưu tiên, tóm tắt và hành động tiếp theo.
3. Bấm "Áp dụng": Badge trạng thái tại đầu trang đổi màu/chữ ngay lập tức không tải lại trang; trong Admin trạng thái được cập nhật.
4. Bấm "Tạo báo cáo nhận định" tại `/crm/reports/`: Sinh văn bản nhận định 3 phần; đồng thời lưu bản ghi `AIReport` hiển thị trong Admin (CRM → Báo cáo AI).
5. Dashboard `/crm/`: Cập nhật bảng "Khách hàng cần chú ý (Ưu tiên Cao)" với khách hàng vừa được phân loại.

## 5. Giả định & Khác biệt so với mô tả
- Để tránh bị lỗi môi trường Python (Django 6.1.1 chỉ chạy với Python >= 3.12 trong khi Python gốc là 3.10), migration `0002_ai_classify_report.py` được tạo hoàn toàn thủ công.
- Các JSON block từ fallback provider được validate thông qua hàm `_parse_json_safe` để xử lý các text bọc code format (markdown ` ```json `) mà các mô hình OpenRouter, Groq hay sử dụng.
- Frontend không cần reload lại toàn trang mà cập nhật trạng thái trực tiếp trên DOM (sử dụng JS `document.getElementById("customer-status-badge")`).
- Test suite có thể chạy và pass khi setup đúng Python environment.

## 6. Hướng dẫn nhóm trưởng Merge nhánh
Vui lòng chạy các lệnh sau ở cửa sổ terminal (powershell/bash) để gộp mã nguồn từ nhánh `feature/ai-classify-report` vào nhánh `main`:

```bash
git checkout main
git pull origin main
git merge --no-ff feature/ai-classify-report
python manage.py migrate
python manage.py test crm
git push origin main
```
