# TH2 – Kế hoạch: Phân tích dữ liệu thông minh cho SmartCRM với AI và Apache Superset MCP

**Nhiệm vụ theo nhóm** · 5 thành viên · 6 mục checklist · dự kiến 4 tuần

| Tài liệu | Dùng để |
|---|---|
| [th2/HOP_DONG_DU_LIEU.md](th2/HOP_DONG_DU_LIEU.md) | **Luật chung**: tên bảng, cột, phương pháp, chỉ số, nhánh git, file của ai. Đọc trước khi làm |
| [th2/prompts/](th2/prompts/) | Prompt cho từng người, copy dán vào Claude Code |

## 1. Phân công

| # | Người | Vai trò | Checklist | Prompt |
|---|---|---|---|---|
| 1 | **Tùng** (nhóm trưởng) | Kiến trúc, dữ liệu thật, Superset MCP, module cảm xúc, tích hợp | 01, 03, 06 (+ 02, 05) | [01_tung_nhom_truong.md](th2/prompts/01_tung_nhom_truong.md) |
| 2 | **Ngọc Anh** | Module dự báo doanh thu | 02, 05, 06 | [02_ngoc_anh_du_bao.md](th2/prompts/02_ngoc_anh_du_bao.md) |
| 3 | **Thái Anh** | Module dự đoán khách rời bỏ | 02, 05, 06 | [03_thai_anh_roi_bo.md](th2/prompts/03_thai_anh_roi_bo.md) |
| 4 | **Hoàng Anh** | Dashboard "SmartCRM – AI Insights" (qua MCP) | 03, 04 | [04_hoang_anh_dashboard.md](th2/prompts/04_hoang_anh_dashboard.md) |
| 5 | **Hoàng Hưng** | Kiểm thử, đối chiếu số liệu, báo cáo, video | 05 | [05_hoang_hung_kiem_thu_bao_cao.md](th2/prompts/05_hoang_hung_kiem_thu_bao_cao.md) |

**Tùng** – Kiến trúc, dữ liệu, Superset MCP và module cảm xúc
- Thiết kế kiến trúc SmartCRM → PostgreSQL → Superset; vẽ sơ đồ luồng dữ liệu.
- Nạp dữ liệu thật (Online Retail II + bộ nhận xét tiếng Việt có nhãn) vào CSDL `smartcrm_th2`; tạo app `insights`, lệnh
  `run_ai_pipeline`, `seed_ai_demo`, schema `ai`.
- Cấu hình Superset MCP, tài khoản quyền hạn chế; dựng 4 biểu đồ tab Tổng quan bằng câu lệnh qua MCP; demo trực tiếp.
- Module phân tích cảm xúc: từ điển từ khoá và Gemini, đánh giá Accuracy, macro F1, chi phí.
- Nhúng dashboard vào SmartCRM; review, gộp code; viết mục đề xuất mở rộng (06).

**Ngọc Anh** – Dự báo doanh thu
- So 3 phương pháp: cùng kỳ năm trước, Holt-Winters, SARIMA; backtest 6 tháng, MAE, RMSE, MAPE.
- Lưu dự báo 6 tháng tới kèm khoảng tin cậy vào `RevenueForecast`; viết mục đánh giá theo khung chung.

**Thái Anh** – Dự đoán khách rời bỏ
- So 3 phương pháp: luật RFM, Logistic Regression, Random Forest; AUC, Precision, Recall, ma trận nhầm lẫn.
- Lưu xác suất rời bỏ từng khách vào `ChurnScore`; hiện "Rủi ro rời bỏ" trên trang chi tiết khách; viết mục đánh giá.

**Hoàng Anh** – Dashboard
- Dựng dashboard "SmartCRM – AI Insights" 4 tab (Tổng quan, Dự báo, Rời bỏ, Cảm xúc) bằng câu lệnh qua MCP, kiểm tra số
  liệu từng biểu đồ bằng SQL; tuần 1–2 dùng dữ liệu giả, tuần 3 nối dữ liệu thật; xuất dashboard; viết mục dashboard.
- Không sửa code SmartCRM.

**Hoàng Hưng** – Kiểm thử và báo cáo
- Cài đặt thử từ đầu theo hướng dẫn, ghi lỗi; lệnh kiểm tra tự động `verify_ai_results` (chỉ đọc) và test.
- Đối chiếu số liệu dashboard với SQL; gộp báo cáo `docs/TH2_BAO_CAO.md`; viết kịch bản video.
- Không sửa code lõi (chỉ thêm lệnh kiểm tra và test của mình).

## 2. Checklist ↔ việc làm ↔ bằng chứng

| Mục | Việc làm | Bằng chứng | Người |
|---|---|---|---|
| **01** Kiến trúc kết nối CRM → CSDL trung tâm | Sơ đồ 4 tầng; nạp dữ liệu thật; schema `analytics`, `ai`; phân quyền tài khoản | `01_kien_truc.md`, lệnh `import_th2_data`, `sql/superset/03_ai_views.sql` | Tùng |
| **02** Mô hình AI phân tích dữ liệu | Dự báo doanh thu, rời bỏ, cảm xúc (cả 3 ví dụ của đề); lệnh chạy toàn chuỗi | Bảng `insights_*`, view `ai.*`, `run_ai_pipeline` | Ngọc Anh, Thái Anh, Tùng |
| **03** Superset MCP kết nối dữ liệu và xây biểu đồ | Cài MCP, tài khoản hạn chế; biểu đồ tạo bằng câu lệnh | `05_mcp.md` (câu lệnh + ảnh), demo trực tiếp trong video | Tùng, Hoàng Anh |
| **04** Kết quả AI lên dashboard | Dashboard AI Insights 4 tab, bộ lọc; nhúng vào `/crm/analytics/`; rủi ro trên trang khách | `06_dashboard.md`, file xuất dashboard, ảnh | Hoàng Anh, Tùng, Thái Anh |
| **05** Báo cáo luồng dữ liệu và đánh giá mô hình | Khung đánh giá chung cho 3 mô hình; kiểm tra tự động; đối chiếu dashboard | `TH2_BAO_CAO.md`, `verify_ai_results`, `08_kiem_thu_doi_chieu.md` | Hoàng Hưng, Ngọc Anh, Thái Anh, Tùng |
| **06** Đề xuất nhiều mô hình (cộng điểm) | 3 bài toán × 2–3 phương pháp; 4 họ phương pháp; đề xuất K-Means, phát hiện bất thường, bán chéo | Bảng so sánh trong từng mục đánh giá, `07_de_xuat_mo_rong.md` | Tùng, Ngọc Anh, Thái Anh |

## 3. Lịch 4 tuần

| Tuần | Tùng | Ngọc Anh, Thái Anh | Hoàng Anh | Hoàng Hưng |
|---|---|---|---|---|
| 1 | Giai đoạn A: CSDL, dữ liệu thật, app `insights`, dữ liệu giả – **gộp sớm nhất**; bắt đầu B (MCP) | Cài môi trường, đọc hợp đồng, bắt đầu khi A đã gộp | Giai đoạn 1: cài đặt, cấu hình MCP | Giai đoạn 1: cài đặt thử, ghi lỗi tài liệu |
| 2 | B: MCP, 4 biểu đồ Tổng quan; C: module cảm xúc | Viết module, test, chạy thật | Dựng biểu đồ trên dữ liệu giả | Lệnh `verify_ai_results`, khung báo cáo |
| 3 | C xong; D: review, chạy toàn chuỗi, nhúng dashboard | Sửa theo review, viết mục đánh giá | Giai đoạn 2: nối dữ liệu thật, kiểm tra lại, xuất | Theo dõi, nhắc các mục báo cáo |
| 4 | D: đề xuất mở rộng, kiến trúc hoàn chỉnh, diễn tập | Hoàn thiện | Ảnh, nhận định kinh doanh | Giai đoạn 2: đối chiếu, gộp báo cáo, kịch bản video |

## 4. Quy tắc chung
- Mỗi người một nhánh (xem hợp đồng mục 1), mở Pull Request vào `th2/main`, Tùng review rồi gộp.
- Hoàng Anh và Hoàng Hưng **không sửa code lõi** (models, migrations, pipeline, crm, sql, superset, docker-compose).
- Ghi kết quả **đúng cấu trúc trong hợp đồng**; muốn đổi thì báo Tùng.
- Toàn bộ `python manage.py test` phải qua trước khi mở Pull Request.
- Không commit `.env`, mật khẩu, thư mục `data/`.
- Họp ngắn mỗi tuần; ai kẹt báo ngay.

## 5. Rủi ro

| Mức | Rủi ro | Cách xử lý |
|---|---|---|
| Cao | MCP cộng đồng không chạy với Superset 4.1.2 | Tùng thử ngay tuần 1; phương án B là Superset 6.x riêng có MCP chính thức. Hoàng Anh có hướng dẫn dựng bằng giao diện |
| Cao | Giai đoạn A của Tùng chậm, cả nhóm chờ | A ưu tiên số 1; Hoàng Anh làm trước trên dữ liệu giả `seed_ai_demo` |
| Vừa | Hết hạn mức Gemini | Chấm theo lô, giới hạn 600 câu mẫu, có AI dự phòng |
| Vừa | Dữ liệu là shop nước ngoài, văn bản gắn nhân tạo | Ghi rõ trong mục Hạn chế của báo cáo |
