# 02. Dự báo doanh thu

## 1. Bài toán và câu hỏi kinh doanh

Module dự báo trả lời câu hỏi: trong sáu tháng tới, tổng doanh thu mỗi tháng của
shop có thể là bao nhiêu và khoảng dao động hợp lý là bao nhiêu? Kết quả dành cho
người quản lý và nhóm phân tích để lập kế hoạch bán hàng, dòng tiền và tồn kho.
Module chỉ dự báo tổng doanh thu theo tháng, không dự báo theo từng sản phẩm hoặc
từng khách hàng.

## 2. Dữ liệu

Nguồn dữ liệu là Online Retail II. Dữ liệu được lấy mẫu 2.000 khách với
`random_state=42`, dời thời gian thêm 14 năm và quy đổi theo tỷ giá cố định
`1 GBP = 33.000 VNĐ`. Hóa đơn có mã bắt đầu bằng `C` được xem là đơn huỷ và
không tính doanh thu; doanh thu là tổng `quantity × unit_price` của đơn hoàn
thành theo quy ước TH1.

Sau khi nạp có 14.680 đơn, trong đó 2.370 đơn huỷ, 255.715 dòng sản phẩm và
4.424 sản phẩm. Ngày tham chiếu là 09/12/2025. Chuỗi dùng cho mô hình gồm 24
tháng trọn vẹn từ 12/2023 đến 11/2025, các tháng không có đơn được điền bằng 0.
Tổng chuỗi 24 tháng dùng trong mô hình là 177.385.266.960 VNĐ. Doanh thu đơn
hoàn thành toàn bộ dữ liệu trước khi loại tháng chưa trọn vẹn là
186.513.155.070 VNĐ.

## 3. Phương pháp

- **Seasonal naive:** dự báo tháng kế tiếp bằng doanh thu của cùng tháng năm
  trước (độ trễ 12 tháng). Khoảng tin cậy 95% được tính bằng dự báo cộng/trừ
  `1,96 × độ lệch chuẩn sai số` trên phần huấn luyện.
- **Holt-Winters:** dùng `statsmodels.ExponentialSmoothing` với xu hướng cộng,
  mùa vụ cộng, chu kỳ 12 tháng và `initialization_method="estimated"`. Khoảng
  tin cậy 95% lấy bằng **mô phỏng 1.000 lần** (`simulate`, phân vị 2,5% – 97,5%) nên
  **rộng dần theo số tháng dự báo** – phản ánh đúng việc càng dự báo xa càng kém chắc
  chắn (nếu mô phỏng lỗi thì dùng ±1,96 × độ lệch sai số, ghi trong `notes`). Mô hình
  luôn thử bản có mùa vụ trước; khi backtest chỉ có 18 tháng (chưa đủ 2 chu kỳ),
  statsmodels báo không tính được hệ số mùa vụ ban đầu nên dùng bản không mùa vụ
  – ghi trong `notes` và `params.model` của lần chạy. Dự báo 6 tháng tới (24 tháng
  huấn luyện) dùng bản có mùa vụ.
- **SARIMA:** dùng `SARIMAX` (tham số mặc định của statsmodels) với
  `order=(1,1,1)` và `seasonal_order=(0,1,1,12)` khi có đủ 24 tháng; chuỗi ngắn hơn
  thử `(0,1,0,12)` rồi `(1,1,1)` không mùa vụ. Cấu hình nào lỗi hoặc cho dự báo
  **phân kỳ** (vượt 3 lần doanh thu tháng cao nhất) thì bị loại và chuyển cấu hình
  sau; cấu hình thực dùng ghi trong `params` và `notes`. Khoảng tin cậy lấy từ
  `get_forecast().conf_int(alpha=0.05)`. Các giá trị âm được cắt về 0.

## 4. Cách đánh giá

Sáu tháng cuối được giữ làm tập kiểm tra; 18 tháng đầu dùng huấn luyện. Mỗi
phương pháp dự báo sáu tháng kiểm tra rồi được huấn luyện lại trên toàn bộ 24
tháng để dự báo sáu tháng tiếp theo. MAE là trung bình số tiền dự báo lệch bao
nhiêu đồng mỗi tháng. RMSE cũng đo độ lệch nhưng phạt mạnh hơn các sai số lớn.
MAPE là trung bình phần trăm lệch; các tháng có doanh thu thực tế bằng 0 được
bỏ qua khi tính MAPE.

## 5. Kết quả

Mã batch: `20261017-170211`. Chỉ số tính trên dự báo đã làm tròn đến đồng – đúng giá
trị lưu trong `RevenueForecast`, nên tính lại được từ các dòng `backtest`.

| Phương pháp | MAE (VNĐ) | RMSE (VNĐ) | MAPE (%) | Huấn luyện | Kiểm tra | Được chọn |
|---|---:|---:|---:|---:|---:|---|
| seasonal_naive | 1.657.659.575 | 1.847.696.404 | 20,3593 | 18 | 6 | Có |
| sarima | 2.792.891.919 | 3.176.278.363 | 29,4439 | 18 | 6 | Không |
| holt_winters | 2.905.651.300 | 3.290.414.554 | 29,7908 | 18 | 6 | Không |

Mỗi phương pháp thành công và ghi đủ 18 dòng `history`, 6 dòng `backtest` và
6 dòng `future`. `seasonal_naive` được chọn vì có MAPE nhỏ nhất.

Chi tiết 6 tháng kiểm tra (tỷ VNĐ):

| Tháng | Thực tế | seasonal_naive | holt_winters | sarima |
|---|---:|---:|---:|---:|
| 06/2025 | 8,79 | 6,75 | 6,89 | 7,82 |
| 07/2025 | 5,59 | 7,40 | 6,98 | 7,20 |
| 08/2025 | 5,79 | 7,14 | 7,07 | 7,58 |
| 09/2025 | 10,21 | 7,24 | 7,16 | 7,35 |
| 10/2025 | 12,56 | 11,01 | 7,26 | 7,49 |
| 11/2025 | 11,86 | 12,10 | 7,35 | 7,40 |

Ghi chú của lần chạy: Holt-Winters backtest dùng bản không mùa vụ (18 tháng); SARIMA
backtest loại cấu hình `(1,1,1)×(0,1,0,12)` (lỗi LU decomposition) và dùng `(1,1,1)`
không mùa vụ. Vì vậy hai mô hình này dự báo gần như phẳng (≈ 7–7,5 tỷ) và bỏ lỡ đỉnh
tháng 10 – 11.

**Dự báo 6 tháng tới** (phương pháp được chọn, tỷ VNĐ, khoảng tin cậy 95%):
12/2025 **6,92** (3,64 – 10,19) · 01/2026 3,96 (0,68 – 7,23) · 02/2026 4,33 ·
03/2026 5,53 · 04/2026 4,85 · 05/2026 6,80 – tổng ≈ 32,4 tỷ.

## 6. Kết luận

Với batch này, `seasonal_naive` là phương pháp phù hợp nhất trong ba phương
pháp theo tiêu chí MAPE. Kết quả cho thấy việc lặp lại doanh thu cùng tháng của
năm trước phù hợp hơn Holt-Winters và SARIMA trên chuỗi 24 tháng hiện có: với 18 tháng
huấn luyện, hai mô hình thống kê không học được mùa vụ nên bỏ lỡ đỉnh cuối năm.

## 7. Hạn chế

- Dữ liệu là của một shop ở Anh, đã được dời thời gian và đổi tiền để phục vụ
  bài thực hành; đây không phải dữ liệu vận hành hiện tại của shop tại Việt Nam.
- Số tháng quan sát ít (24 tháng), nên việc đánh giá mùa vụ và độ ổn định của
  mô hình còn hạn chế.
- Chỉ dự báo tổng doanh thu theo tháng, chưa dự báo theo sản phẩm, nhóm sản
  phẩm, khách hàng hoặc kênh bán.
- Khoảng tin cậy là ước lượng thống kê, không phải cam kết doanh thu thực tế.

## 8. Cách chạy lại

```powershell
.venv\Scripts\Activate.ps1
python manage.py run_ai_pipeline --only forecast
python manage.py test
```

Kết quả được ghi vào `ModelRun` và `RevenueForecast` trong batch mới. View
`ai.revenue_forecast` sẽ tự lấy batch thành công mới nhất sau khi tầng view
Superset đã được cài đặt.
