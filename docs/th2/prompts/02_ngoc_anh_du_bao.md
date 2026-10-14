# Prompt TH2 – Ngọc Anh: Module dự báo doanh thu

> **Cách dùng:** chỉ bắt đầu khi Tùng báo đã gộp giai đoạn A vào `th2/main`. Mở Claude Code tại thư mục `smartcrm/`,
> dán toàn bộ khối dưới đây. Agent sẽ tự kiểm tra điều kiện, làm, chạy test và báo lại.

```text
Bạn là kỹ sư khoa học dữ liệu Python làm việc trong repo SmartCRM (Wagtail 8/Django 6, Python 3.13, PostgreSQL).
Tôi là Ngọc Anh, thành viên nhóm TH2 "Hệ thống phân tích dữ liệu thông minh tích hợp AI và Apache Superset".
Phần của tôi: MODULE DỰ BÁO DOANH THU (checklist 02, 05, 06).

BƯỚC 0 – ĐỌC VÀ KIỂM TRA (bắt buộc):
- Đọc HẾT docs/th2/HOP_DONG_DU_LIEU.md. Tên bảng, tên trường, tên phương pháp, khoá metrics, hằng số phải đúng y như file
  này. Nếu thấy mâu thuẫn hoặc thiếu, DỪNG LẠI và nói rõ cần hỏi Tùng điều gì – không tự đổi hợp đồng.
- Đọc insights/models.py, insights/conf.py, insights/pipeline/__init__.py, crm/models.py (Order, OrderItem),
  crm/analytics.py (hàm monthly_revenue: quy ước doanh thu của TH1).
- Kiểm tra: `git branch` có th2/main; `python manage.py showmigrations insights` có 0001_initial [X];
  `python -c "import pandas, statsmodels"` chạy được. Thiếu điều kiện nào thì DỪNG LẠI báo tôi, không tự tạo thay.
- Tạo nhánh: git checkout th2/main && git pull (nếu có remote) && git checkout -b th2/du-bao

BƯỚC 1 – CHUỖI DOANH THU THÁNG:
Viết hàm lấy doanh thu theo tháng từ ORM: Σ quantity × unit_price của đơn status="completed", gom theo tháng giờ
Asia/Ho_Chi_Minh, từ tháng đầu có đơn đến tháng trọn vẹn cuối cùng tính theo insights.conf.reference_date() (bỏ tháng
chưa hết). Tháng không có đơn = 0. Trả về pandas Series có tần suất tháng (MS). Kiểm tra tổng chuỗi bằng tổng doanh thu
đơn Hoàn thành trong cùng khoảng.

BƯỚC 2 – 3 PHƯƠNG PHÁP (file insights/pipeline/forecast.py, hàm run(batch) -> list[ModelRun]):
- seasonal_naive: dự báo tháng t = doanh thu tháng t−12. Nếu chưa đủ 12 tháng lịch sử thì dùng tháng liền trước và ghi notes.
  Khoảng tin cậy 95% = dự báo ± 1,96 × độ lệch chuẩn sai số trên tập huấn luyện.
- holt_winters: statsmodels ExponentialSmoothing, trend="add", seasonal="add", seasonal_periods=12 khi có ≥ 24 tháng
  huấn luyện; ít hơn thì bỏ seasonal và ghi notes. Khoảng tin cậy 95% bằng mô phỏng (simulate) hoặc theo độ lệch sai số,
  ghi rõ cách làm trong params.
- sarima: statsmodels SARIMAX order=(1,1,1), seasonal_order=(0,1,1,12) khi có ≥ 24 tháng huấn luyện, ngược lại (1,1,1)
  không mùa vụ. Khoảng tin cậy 95% từ get_forecast().conf_int().
Dự báo không được âm: cắt về 0 và ghi notes nếu xảy ra.

BƯỚC 3 – ĐÁNH GIÁ (backtest):
- Giữ lại BACKTEST_MONTHS (6) tháng cuối làm tập kiểm tra, huấn luyện trên phần trước đó, dự báo 6 tháng đó.
- Chỉ số: mae, rmse, mape (%, bỏ qua tháng có doanh thu thật = 0 và ghi số tháng bị bỏ), n_train, n_test.
  Làm tròn 4 chữ số.
- is_selected = phương pháp có mape nhỏ nhất. Phương pháp lỗi → status="failed", notes ghi lỗi, các phương pháp khác vẫn chạy.

BƯỚC 4 – GHI KẾT QUẢ (đúng mục 4 hợp đồng, bảng RevenueForecast):
Với MỖI phương pháp, 1 ModelRun(module="forecast", method=...) và các dòng:
- kind="history": mọi tháng huấn luyện, chỉ có actual.
- kind="backtest": 6 tháng kiểm tra, có actual, forecast, lower, upper.
- kind="future": huấn luyện lại trên TOÀN BỘ chuỗi rồi dự báo FORECAST_HORIZON (6) tháng tiếp theo, chỉ có forecast,
  lower, upper.
Tiền làm tròn đến đồng. Mỗi phương pháp ghi trong transaction.atomic(). Đăng ký "forecast" vào MODULES trong
insights/pipeline/__init__.py (chỉ thêm đúng dòng của mình, không sửa phần khác).

BƯỚC 5 – TEST (insights/tests/test_forecast.py), dùng dữ liệu giả tự tạo trong test, không phụ thuộc dữ liệu nạp:
- Chuỗi doanh thu: đơn Huỷ không tính, tháng trống = 0, bỏ tháng chưa trọn.
- Chuỗi giả có mùa vụ rõ (36 tháng): cả 3 phương pháp chạy, đủ khoá metrics, đúng 1 is_selected, đủ 3 loại kind, số
  tháng future = 6, lower ≤ forecast ≤ upper.
- Chuỗi ngắn (14 tháng): không lỗi, có notes cảnh báo.
Chạy `python manage.py test` – TOÀN BỘ test (kể cả của người khác) phải qua.

BƯỚC 6 – CHẠY THẬT: `python manage.py run_ai_pipeline --only forecast`. In bảng so sánh 3 phương pháp. Nếu đã có quyền
chạy SQL thì kiểm tra `SELECT kind, count(*) FROM ai.revenue_forecast GROUP BY kind;` (nếu view chưa cập nhật thì báo tôi
nhờ Tùng chạy lại sql/superset/03_ai_views.sql).

BƯỚC 7 – BÁO CÁO: viết docs/th2/bao_cao/02_du_bao.md theo ĐÚNG "Khung bắt buộc" mục 9 của hợp đồng (8 phần). Số liệu
lấy từ ModelRun của batch vừa chạy, ghi mã batch. Giải thích chỉ số bằng lời dễ hiểu (MAE = trung bình lệch bao nhiêu
đồng mỗi tháng, MAPE = lệch bao nhiêu phần trăm). Phần hạn chế phải nêu: dữ liệu là của một shop ở Anh đã dời thời gian và
đổi tiền; số tháng ít; chỉ dự báo tổng doanh thu.

RÀNG BUỘC:
- Chỉ tạo/sửa: insights/pipeline/forecast.py, insights/tests/test_forecast.py, docs/th2/bao_cao/02_du_bao.md, và đúng 1
  dòng đăng ký trong insights/pipeline/__init__.py. Không sửa models, migrations, file của người khác, .env.
- Không thêm thư viện ngoài pandas, numpy, statsmodels, scikit-learn đã có. Không gọi mạng.
- Commit nhỏ theo từng bước bằng tài khoản git của tôi. KHÔNG push – để tôi tự xem rồi push và mở Pull Request vào th2/main.

KẾT THÚC: báo cáo ngắn gồm file đã tạo/sửa, kết quả test, bảng so sánh 3 phương pháp (mae, rmse, mape, phương pháp được
chọn), mã batch, và những việc tôi cần làm tiếp (push, mở PR, báo Hoàng Anh/Hoàng Hưng).
```
