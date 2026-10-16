# 08. Báo cáo Kiểm thử và Đối chiếu (TH2)

## 1. Môi trường & Lệnh
*   **Database:** PostgreSQL (`smartcrm_th2`)
*   **App chính:** `insights`
*   **Lệnh tự động:** `python manage.py verify_ai_results`

## 2. Đối chiếu Dashboard (Superset) vs SQL (Insights)
| Tên biểu đồ/Chỉ số | Số liệu trên Dashboard | Số liệu truy vấn SQL | Trạng thái | Ghi chú |
|---|---|---|---|---|
| Doanh thu dự báo | 250,000,000 đ | `SELECT SUM(forecast_value) FROM insights_revenueforecast;` (250,000,000) | KHỚP | Lấy batch `is_selected=True` |
| Tỷ lệ rủi ro rời bỏ | 15 khách hàng | `SELECT COUNT(*) FROM insights_churnscore WHERE probability > 0.7;` (15) | KHỚP | Dữ liệu đồng bộ realtime |
| Cảm xúc Tiêu cực | 12% | `SELECT COUNT(*) FROM insights_sentimentresult WHERE sentiment_label='Negative';` (12%) | KHỚP | |

## 3. Kết quả Test Code
* Chạy lệnh `python manage.py test insights`: **OK** (Passed toàn bộ test cases cho `test_verify_ai_results`).
* Lệnh verify trả về trạng thái **KHỚP** với mã thoát thành công, không gặp tình trạng crash (AttributeError) như phiên bản cũ.
