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
  - `crm/migrations/0003_customer_ai_provider.py`: thêm `Customer.ai_provider` (sửa sau review).
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
- `python manage.py test crm`: **65 test – OK** (40 test cũ + 25 test mới). `makemigrations --check`: không còn thay đổi.
- Test mới không gọi mạng: mọi lời gọi AI được mock (`GeminiCRMService.client`, `httpx.post` hoặc method service) và cấu hình được cô lập bằng `override_settings` (`LIVE`, `FALLBACK`, `AI_MOCK=True`). Đã kiểm tra: chạy với `AI_MOCK=True` trong môi trường vẫn PASS.
- Nội dung chính:
  - `analyze_customer`: prompt chứa dữ liệu khách và dùng JSON schema; JSON hợp lệ → lưu đủ trường `ai_*` + `ai_provider`, không đổi `status`; JSON sai → `AIServiceError`; giá trị lạ/sai kiểu → `neutral`/`medium`/giữ trạng thái; `next_actions` cắt còn 3 chuỗi; JSON bọc ```` ```json ```` hoặc có lời dẫn; AI dự phòng; MOCK không gọi AI.
  - `build_report_stats`/`generate_report`: số khách/đơn theo trạng thái, doanh thu, top khách, cảm xúc khớp dữ liệu tạo trong test; `json.dumps(stats)` chạy được; prompt chứa số liệu; nhận định MOCK chỉ dùng số liệu thật.
  - API: analyze 200 (có `provider`, `can_apply`, giờ Việt Nam)/404/405/503; apply-status 200 (+ `badge_class`)/400; 401/403 JSON cho cả 3 API mới; generate-report 200 + lưu `AIReport`/503/CSDL rỗng → 400 và **không gọi AI**.
  - Trang: `/crm/reports/` yêu cầu đăng nhập; link "Báo cáo AI" có ở **mọi** trang `/crm/`; Admin "Báo cáo AI" chỉ xem; `seed_demo --analyze` không gọi AI và chạy lại được.

## 4. Bảng kết quả kiểm tra luồng API AI (Mục B, C, D)
Chạy ngày 27/09/2026 (nhóm trưởng kiểm lại sau review) trên bản sao CSDL sau `seed_demo --reset --analyze`, gọi API qua Django test client với tài khoản staff. Sau đó chạy E2E trên Google Chrome thật bằng Playwright: 26/26 kiểm tra PASS (xem `docs/TEST_CASES.md` mục 4).

### B. Ma trận chế độ AI
| Chế độ | Kết quả thực tế |
|---|---|
| 1. MOCK | **Đạt** – cả 3 API trả 200, `mock: true`; `can_apply` chỉ `true` khi đề xuất khác trạng thái hiện tại |
| 2. Gemini thật | **Đạt** – Gợi ý phản hồi 200; Báo cáo 200 đủ 3 phần, số liệu khớp thẻ số; Phân loại lần 1 trả 503 "Máy chủ Gemini đang quá tải…", lần 2 trả 200 qua model dự phòng, JSON hợp lệ |
| 3. AI dự phòng | **Chưa chạy thật** – chưa có key Groq/OpenRouter; chỉ có unit test giả lập |
| 4. Key sai | **Đạt** – cả 3 API trả 503 "API key Gemini không hợp lệ…", không lộ key |
| 5. Quá tải / hết quota | **Đạt với quá tải (gặp tự nhiên)**; hết quota (429) và chuyển sang AI dự phòng chỉ kiểm bằng unit test |

### C. Kiểm tra từng API
| Endpoint | Kết quả thực tế |
|---|---|
| `suggest-reply` / `save-interaction` (cũ) | Đạt – 40 test cũ PASS, gọi thật với Gemini trả 200 |
| `POST …/analyze/` | Đạt – 200 đủ trường `data` + `provider`; 404; 405; 503 khi AI lỗi |
| `POST …/apply-status/` | Đạt – 200 trả `status`, `status_display`, `badge_class`; 400 khi chưa có hoặc trùng đề xuất |
| `POST /crm/api/reports/generate/` | Đạt – 200 đủ `stats, insight, generated_at, mock, provider`; lưu `AIReport`; CSDL rỗng → 400 không gọi AI |
| Mọi API mới | Đạt – chưa đăng nhập 401 JSON, không phải staff 403 |

### D. Luồng dữ liệu Admin → AI → Frontend → CSDL → Admin
Đã kiểm bằng API/HTML: kết quả phân tích lưu vào `Customer.ai_*`, hiện ở trang chi tiết, danh sách (lọc `?priority=`), Tổng quan và Admin (cột/bộ lọc + panel "Phân tích AI"); báo cáo lưu `AIReport`, xem được ở Admin (chỉ xem). Các bước bấm nút trên trình duyệt đã chạy E2E: Đạt, không lỗi JS, màn 375px không tràn ngang.

## 5. Giả định & Khác biệt so với mô tả
- Migration `0002_ai_classify_report.py` do thành viên viết tay (máy dùng Python 3.10). Nhóm trưởng đã kiểm tra bằng `makemigrations --check` trên Python 3.13: khớp model.
- Thêm migration `0003_customer_ai_provider.py`: trường `Customer.ai_provider` lưu tên AI đã phân tích (kèm "(chế độ mô phỏng)" nếu là MOCK) để hiển thị đúng sau khi tải lại trang.
- API `analyze` trả thêm `data.status` và `data.can_apply` để giao diện chỉ hiện nút "Áp dụng" khi đề xuất khác trạng thái hiện tại.
- API `generate` trả thêm `report` (thời điểm, người tạo) để cập nhật bảng "5 báo cáo gần nhất" không cần tải lại trang.
- `AIReport` trong Admin dùng permission policy chỉ xem (không thêm/sửa/xoá, kể cả superuser); bản ghi chỉ được tạo từ `/crm/reports/`.
- Chuỗi JSON từ AI dự phòng được parse bằng `_parse_json_safe` (chịu được ```` ```json ```` và lời dẫn trước/sau JSON).

### Sửa sau review của nhóm trưởng
- Giờ phân tích trong API trả theo UTC (lệch 7 tiếng) → đổi sang giờ Việt Nam.
- Nút "Áp dụng" hiện cả khi đề xuất trùng trạng thái → dùng `can_apply`.
- Form "Thêm" AIReport trong Admin tạo được bản ghi rỗng → chỉ xem.
- `build_report_stats` lặp từng khách (N+1 truy vấn) → dùng `annotate`/`values().annotate(Count)`.
- Nhận định MOCK có câu không dựa trên số liệu → mọi câu suy từ stats.
- Tổng quan: giữ nguyên bảng "5 tương tác mới nhất" như bản gốc, thêm bảng "✨ Khách hàng ưu tiên cao (theo AI)".
- Test cô lập cấu hình, bổ sung test còn thiếu; tài liệu ghi đúng kết quả thật.

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
