# 6. Kiểm thử và đối chiếu số liệu (checklist 05)

*Người viết: Hoàng Hưng · Lệnh: `insights/management/commands/verify_ai_results.py` ·
Test: `insights/tests/test_verify_ai_results.py` · Ngày chạy: 17/10/2026 · CSDL `smartcrm_th2`*

Nhóm kiểm tra theo **4 lớp**: (1) test tự động cho từng module; (2) lệnh `verify_ai_results` tính lại số liệu **độc lập**
rồi so với kết quả mô hình đã lưu; (3) đối chiếu từng biểu đồ dashboard với SQL; (4) kiểm tra trên giao diện SmartCRM.

## 6.1. Test tự động

`python manage.py test` – **161 test, tất cả qua** (17/10/2026).

| File | Kiểm tra gì |
|---|---|
| `insights/tests/test_import_th2_data.py` | Quy ước nạp dữ liệu: dời +14 năm, đổi tiền, hoá đơn `C` → Huỷ, bỏ dòng giá 0 / không mã khách, nạp lại ra cùng kết quả, chặn CSDL không phải `_th2` |
| `insights/tests/test_pipeline.py` | `run_method` ghi lỗi không dừng pipeline; `select_best` chọn đúng 1; `run_ai_pipeline` chỉ xoá batch demo của module đang chạy |
| `insights/tests/test_forecast.py` | 3 phương pháp ghi đủ dòng history/backtest/future, lower ≤ forecast ≤ upper; chuỗi ngắn có cảnh báo; metrics tính lại được từ dòng backtest; chặn SARIMA phân kỳ; MAPE = None khi không có tháng khác 0 |
| `insights/tests/test_churn.py` | Nhãn đúng cửa sổ (cutoff, R]; đặc trưng không dùng dữ liệu sau cutoff; 3 phương pháp đủ khoá metrics, xác suất trong [0, 1]; trang khách hiện điểm, ưu tiên batch thật hơn demo, "Chưa có dự đoán" khi trống |
| `insights/tests/test_sentiment.py` | Từ điển + phủ định; 2 phương pháp chấm cùng tập mẫu; JSON hỏng của AI không làm sập; AI lỗi → `failed`; chế độ mô phỏng không được chọn |
| `insights/tests/test_verify_ai_results.py` | Dữ liệu đúng → tất cả KHỚP (A–D); sửa sai 1 metrics → LỆCH, thoát mã 1; chọn sai phương pháp → LỆCH; chỉ có batch demo → cảnh báo; có batch thật thì batch demo bị bỏ qua |

## 6.2. Lệnh `verify_ai_results` (chỉ đọc)

Lệnh kiểm tra **batch thành công mới nhất của từng module** (bỏ qua batch `demo`). Doanh thu tháng được **tính lại bằng
truy vấn riêng** (không dùng `insights.data.monthly_revenue_series` – chính là hàm đang được kiểm tra). Có tuỳ chọn
`--module forecast|churn|sentiment`; có mục LỆCH thì thoát mã 1.

| Nhóm | Nội dung kiểm tra | Dự báo | Rời bỏ | Cảm xúc |
|---|---|---|---|---|
| A. Chung | Đúng 1 phương pháp được chọn · đủ khoá metrics theo hợp đồng · chọn đúng tiêu chí (MAPE min / AUC max / Macro F1 max) | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ |
| B. Dự báo | `actual` 24 tháng khớp doanh thu tự tính (lệch ≤ 1 ₫) · đủ 6 backtest + 6 future · lower ≤ forecast ≤ upper · MAE/RMSE/MAPE tính lại khớp (≤ 0,01) – cho cả 3 phương pháp | 12/12 ✅ | – | – |
| C. Rời bỏ | 2.000/2.000 khách đã mua đến 09/12/2025 đều có điểm · xác suất trong [0, 1] · mức rủi ro đúng ngưỡng 0,6 / 0,3 – cho cả 3 phương pháp | – | 9/9 ✅ | – |
| D. Cảm xúc | Nhãn hợp lệ · accuracy và Macro F1 tính lại từ `SentimentResult` ↔ `SentimentLabel` khớp (≤ 0,001) trên 600 câu | – | – | 4/4 ✅ |
| E. View `ai.*` | Số phương pháp trong `ai.model_run` và số dòng `ai.revenue_forecast` (90) / `ai.churn_score` (6.000) / `ai.interaction_sentiment` (1.200) khớp ORM | 2/2 ✅ | 2/2 ✅ | 2/2 ✅ |

**Kết quả: 40/40 mục KHỚP** (dự báo + rời bỏ: batch `20261017-072049`; cảm xúc: batch `20261014-215419`).
Phương pháp được chọn: dự báo – Cùng kỳ năm trước (MAPE 20,36%); rời bỏ – Logistic Regression (AUC 0,810; Cao 793 ·
Trung bình 484 · Thấp 723); cảm xúc – Từ điển từ khoá (Macro F1 0,582).

## 6.3. Lỗi tìm ra trong quá trình kiểm thử và review

| # | Phát hiện | Lỗi | Người phụ trách | Trạng thái |
|---|---|---|---|---|
| 1 | Chạy lại trên dữ liệu thật | **SARIMA phân kỳ** khi backtest: dự báo tới 543 tỷ/tháng, MAPE 1.415% (báo cáo ghi 20,82%) | Ngọc Anh | ✅ Đã sửa (nhánh `fix/th2-du-bao-roi-bo`): loại cấu hình phân kỳ → MAPE 29,44% |
| 2 | Đối chiếu mục B | MAE/RMSE/MAPE tính trên dự báo chưa làm tròn, không tính lại được từ dòng đã lưu (lệch 0,09 ₫) | Ngọc Anh | ✅ Đã sửa |
| 3 | Đọc `params` | Holt-Winters ghi `additive_seasonal` nhưng thực tế chạy không mùa vụ; MAPE = 0 khi không có tháng khác 0 | Ngọc Anh | ✅ Đã sửa |
| 4 | `python manage.py test` | Test `test_features_stop_before_cutoff…` của module rời bỏ FAIL (kỳ vọng nhãn sai) | Thái Anh | ✅ Đã sửa |
| 5 | Đối chiếu ranh giới | Đơn đúng 0 giờ ngày cutoff không thuộc đặc trưng lẫn nhãn; trang khách có thể hiện điểm batch `demo` | Thái Anh | ✅ Đã sửa |
| 6 | Kiểm tra đủ khoá (mục A) | Chế độ **mô phỏng** của module cảm xúc (khi chưa có API key) không ghi `avg_latency_ms` – sai hợp đồng mục 5. Dữ liệu thật hiện tại không bị ảnh hưởng | Tùng | ✅ Đã sửa (`sentiment.py` ghi `avg_latency_ms = 0`, thêm kiểm tra trong test) |
| 7 | Bảng đối chiếu `05_mcp.md` mục 4.4 | Vẫn ghi số của dữ liệu giả (353 / 926 / 721…) | Tùng | ✅ Đã cập nhật số thật và chụp lại 4 ảnh |

Nội dung đã báo: *Ngọc Anh – SARIMA backtest phân kỳ, metrics tính trên số chưa làm tròn*; *Thái Anh – test nhãn FAIL,
báo cáo chưa có số*; *Tùng – chế độ mô phỏng cảm xúc thiếu `avg_latency_ms`, mục 4.4 còn số demo*.

## 6.4. Đối chiếu dashboard với SQL

Dashboard **SmartCRM – AI Insights** nhúng tại `/crm/analytics/?tab=ai` (máy nhóm trưởng): 4 tab hiển thị không lỗi.
Mỗi biểu đồ: đọc số trên dashboard, chạy câu SQL tương ứng trên view `ai.*` (SQL Lab, tài khoản chỉ đọc) rồi so.

| Biểu đồ | Số trên dashboard | SQL đối chiếu (rút gọn) | Kết quả SQL | Khớp |
|---|---|---|---|---|
| [Tổng quan] Doanh thu thực tế và dự báo | 10/2025 ≈ 12,6 tỷ; 11/2024 ≈ 12,1 tỷ | `actual` theo tháng, `is_selected` | 12.561.500.160 · 12.098.329.980 | ✅ |
| [Tổng quan] Số khách theo mức rủi ro rời bỏ / [Rời bỏ] Số khách theo mức rủi ro | Cao 793 · Trung bình 484 · Thấp 723 | `COUNT(*) … GROUP BY risk_label` | 793 · 484 · 723 | ✅ |
| [Tổng quan] Tỉ lệ cảm xúc | Tích cực 326 · Trung lập 149 · Tiêu cực 125 | `COUNT(*) … GROUP BY label_pred` | 326 · 149 · 125 | ✅ |
| [Dự báo] Doanh thu dự báo tháng tới | 6.915.032.190 | `(ARRAY_AGG(forecast ORDER BY month))[1]`, `kind='future'` | 6.915.032.190 (12/2025) | ✅ |
| [Dự báo] Doanh thu thực tế và dự báo 6 tháng | 01/2026 ≈ 3,96 tỷ; 05/2026 ≈ 6,80 tỷ | `forecast` tháng 2026-01, 2026-05 | 3.956.294.100 · 6.799.698.510 | ✅ |
| [Dự báo] So sánh 3 phương pháp trên 6 tháng kiểm tra | 10/2025: Cùng kỳ 11,0 · SARIMA 7,49 · HW 7,26 tỷ | `forecast` backtest 2025-10 theo method | 11.012.675.850 · 7.486.454.897 · 7.255.454.962 | ✅ |
| [Dự báo] Sai số các phương pháp | MAPE 20,36 · 29,44 · 29,79 | `ai.model_run` module forecast | 20,3593 · 29,4439 · 29,7908 | ✅ |
| [Rời bỏ] 20 khách rủi ro cao nhất | Dòng 1: Khách UK-16446, 100,0% | `ORDER BY probability DESC LIMIT 1` | Khách UK-16446, 0,999996 | ✅ |
| [Rời bỏ] Rủi ro trung bình theo tháng mua gần nhất | 01/2024 ≈ 93%; 11/2025 ≈ 21% | `AVG(probability)` theo tháng đơn gần nhất | 0,934 · 0,213 | ✅ |
| [Rời bỏ] So sánh mô hình | AUC 0,810 · 0,782 · 0,768 | `ai.model_run` module churn | 0,8102 · 0,7820 · 0,7677 | ✅ |
| [Cảm xúc] Cảm xúc theo tháng | 11/2025: Tích cực 22 · Trung lập 10 · Tiêu cực 10 | đếm theo tháng × nhãn | 22 · 10 · 10 | ✅ |
| [Cảm xúc] Cảm xúc theo kênh | Email 244 · Chat 242 · Trực tiếp 60 · Điện thoại 54 | đếm theo `channel` | 244 · 242 · 60 · 54 | ✅ |
| [Cảm xúc] Độ chính xác: từ điển và Gemini | Macro F1 0,582 · 0,575 | `ai.model_run` module sentiment | 0,5824 · 0,5745 | ✅ |
| [Cảm xúc] Dự đoán đúng và sai | Tiêu cực → Tiêu cực: LLM 129 · Từ điển 82 | đếm `label_true = label_pred = 'Tiêu cực'` theo method | 129 · 82 | ✅ |

**15/15 biểu đồ có số được đối chiếu – tất cả khớp** (dòng thứ 2 gồm 2 biểu đồ). Biểu đồ còn lại
*[Tổng quan] Độ chính xác các mô hình* đọc thẳng `ai.model_run` – cùng nguồn với 3 bảng sai số/so sánh ở trên.

## 6.5. Kiểm tra trên SmartCRM

| Trang | Kiểm tra | Kết quả |
|---|---|---|
| `/crm/analytics/?tab=ai` | Tab *AI Insights* nhúng dashboard bằng guest token, đủ 4 tab, không lỗi | ✅ |
| `/crm/analytics/?tab=kinh-doanh` | Dashboard TH1 vẫn hoạt động | ✅ |
| `/crm/customers/<id>/` – Khách UK-16446 | *Rủi ro rời bỏ*: "100% – Cao · Mô hình Logistic Regression"; `ai.churn_score`: 0,999996, *1. Cao* | ✅ khớp |
| `/crm/customers/<id>/` – khách chưa có điểm | "Chưa có dự đoán" (test tự động) | ✅ |
| Đối chiếu trạng thái CRM | Trong 793 khách rủi ro cao: 704 đã *Đã rời bỏ*, **89 vẫn *Đã mua hàng*** → danh sách cần chăm sóc | – |

## 6.6. Kiểm thử hướng dẫn cài đặt

Làm lại các bước của `docs/th2/CAI_DAT.md` trên máy nhóm (dữ liệu đã nạp sẵn):

| Bước | Vấn đề gặp | Cách xử lý | Đề xuất sửa tài liệu |
|---|---|---|---|
| 2. `.env` | Tài liệu ghi "hỏi Tùng các mật khẩu dùng chung" nhưng thực tế mỗi máy tự đặt mật khẩu | Tự tạo chuỗi ngẫu nhiên | Sửa câu này cho rõ |
| 2. `.env` | Quên đổi `DB_NAME=smartcrm_th2` thì SmartCRM đọc CSDL TH1 | Sửa `.env` | Nhấn mạnh hơn |
| 3. Docker | Sau khi khởi động lại máy, Docker Desktop không tự chạy → Django báo *connection timeout* | Mở Docker Desktop, chờ container *healthy* | Thêm vào "Lỗi hay gặp" |
| 9. Chạy web | Còn tiến trình `runserver` cũ giữ cổng 8000 → trình duyệt thấy giao diện cũ | Tắt tiến trình cũ trước khi chạy lại | Thêm vào "Lỗi hay gặp" |
| MCP | `.mcp.json` đặt ở thư mục cha nhưng mở Claude Code tại `smartcrm` → MCP không nạp; mỗi phiên mới báo *Not authenticated* | Đặt `.mcp.json` trong thư mục mở Claude Code; câu đầu tiên "đăng nhập Superset" | Sửa `CAI_DAT_MCP.md` |

## 6.7. Cách chạy lại toàn bộ kiểm tra

```bash
python manage.py test                       # 161 test, OK ngày 17/10/2026
python manage.py run_ai_pipeline            # (nếu cần batch mới)
python manage.py verify_ai_results          # 40 mục, thoát mã 1 nếu có mục LỆCH
python manage.py verify_superset_data       # đối chiếu TH1 (view analytics)
```
