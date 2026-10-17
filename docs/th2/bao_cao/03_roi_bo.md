# Dự đoán khách hàng rời bỏ

> **Trạng thái:** bản nháp triển khai. Chưa có batch thật để điền kết quả; không dùng số liệu giả làm kết quả mô hình.

## 1. Bài toán và câu hỏi kinh doanh

Module ước tính khách hàng nào có nguy cơ không quay lại mua hàng trong 180 ngày tiếp theo. Nhân viên chăm sóc khách hàng có thể ưu tiên liên hệ nhóm rủi ro cao, kiểm tra trải nghiệm gần đây và đề xuất hỗ trợ phù hợp. Điểm rủi ro là tín hiệu tham khảo, không tự động đổi trạng thái khách hàng.

## 2. Dữ liệu

Nguồn bán hàng theo hợp đồng TH2 là Online Retail II, lấy mẫu 2.000 khách có mã khách, dời thời gian thêm 14 năm và quy đổi theo tỷ giá cố định 33.000 VNĐ/GBP. Theo số liệu nạp ghi trong [báo cáo kiến trúc](01_kien_truc.md), dữ liệu hiện có 14.680 đơn (2.370 đơn huỷ), 255.715 dòng sản phẩm và 4.424 sản phẩm; thời gian giao dịch từ 01/12/2023 đến 09/12/2025. Có 24 tháng trọn vẹn từ 12/2023 đến 11/2025. Ngày tham chiếu là **09/12/2025**. Báo cáo kiến trúc ghi nhận 805 khách có trạng thái CRM “Đã rời bỏ”; con số này là trạng thái nghiệp vụ, không thay thế số nhãn churn của tập huấn luyện.

Cutoff bằng ngày tham chiếu trừ 180 ngày. Tập huấn luyện gồm khách có ít nhất một đơn hoàn thành trước cutoff. Nhãn bằng 1 nếu khách không có đơn hoàn thành trong khoảng `(cutoff, ngày tham chiếu]`, bằng 0 nếu có. Đặc trưng chỉ tính từ dữ liệu trước cutoff. Số khách đủ điều kiện, số khách mỗi nhãn và tỷ lệ rời bỏ sẽ được điền sau khi chạy batch thật.

## 3. Phương pháp

- **Quy tắc RFM (`rfm_rule`):** dùng thứ hạng phần trăm của `recency_days`; khách càng lâu chưa mua thì điểm càng cao. Đây là quy tắc không huấn luyện mô hình.
- **Hồi quy logistic (`logistic_regression`):** chuẩn hoá đặc trưng bằng `StandardScaler`, dùng `class_weight="balanced"` và `max_iter=1000`.
- **Rừng ngẫu nhiên (`random_forest`):** dùng 300 cây, `class_weight="balanced"` và `random_state=42`. Năm đặc trưng quan trọng nhất sẽ được ghi trong kết quả batch.

Cả ba phương pháp dùng các đặc trưng recency, frequency, monetary, average order value, tenure, số đơn 90 ngày gần nhất, số đơn huỷ, số sản phẩm khác nhau và số tương tác.

## 4. Cách đánh giá

Dữ liệu được chia ngẫu nhiên thành 70% huấn luyện và 30% kiểm tra, phân tầng theo nhãn, `random_state=42`. AUC đo khả năng xếp khách có nguy cơ cao hơn khách không rời bỏ; 0,5 tương đương đoán ngẫu nhiên, 1 là phân biệt hoàn hảo. Precision trả lời: trong số khách mô hình báo có nguy cơ, bao nhiêu phần trăm thật sự rời bỏ. Recall trả lời: trong số khách thật sự rời bỏ, mô hình phát hiện được bao nhiêu phần trăm. Precision, recall, F1 và accuracy dùng ngưỡng xác suất 0,5. Phương pháp có AUC cao nhất được chọn.

## 5. Kết quả

**Chưa có kết quả batch thật.** Môi trường hiện tại chưa chạy được Django (không tìm thấy thư viện Django), nên chưa thể chạy pipeline hoặc xác nhận cơ sở dữ liệu. Bảng dưới sẽ được cập nhật từ batch cuối; không điền số ước lượng.

| Phương pháp | AUC | Precision | Recall | F1 | Accuracy | n_train | n_test |
|---|---:|---:|---:|---:|---:|---:|---:|
| Quy tắc RFM | Chưa có | Chưa có | Chưa có | Chưa có | Chưa có | Chưa có | Chưa có |
| Hồi quy logistic | Chưa có | Chưa có | Chưa có | Chưa có | Chưa có | Chưa có | Chưa có |
| Rừng ngẫu nhiên | Chưa có | Chưa có | Chưa có | Chưa có | Chưa có | Chưa có | Chưa có |

- **Mã batch:** chưa chạy.
- **Tỷ lệ rời bỏ của tập:** chưa có.
- **Ma trận nhầm lẫn của phương pháp được chọn** (hàng = nhãn thật, cột = dự đoán):

  |  | Dự đoán không rời bỏ | Dự đoán rời bỏ |
  |---|---:|---:|
  | Thật sự không rời bỏ | Chưa có (tn) | Chưa có (fp) |
  | Thật sự rời bỏ | Chưa có (fn) | Chưa có (tp) |

- **Top đặc trưng quan trọng của rừng ngẫu nhiên:** chưa có.
- **Số khách theo mức rủi ro:** chưa có.

## 6. Kết luận

Chưa thể chọn phương pháp tốt nhất trước khi chạy và so sánh AUC trên dữ liệu thực tế. Sau batch, phương pháp được chọn sẽ là run có AUC cao nhất; điểm rủi ro của run đó được hiển thị ở trang chi tiết khách hàng.

Gợi ý cho nhân viên sau khi có kết quả: ưu tiên rà soát nhóm rủi ro cao, xem lịch sử mua hàng và tương tác, sau đó liên hệ để hỏi nhu cầu hoặc xử lý vấn đề còn tồn đọng. Không gửi cùng một nội dung tự động cho mọi khách.

## 7. Hạn chế

Mốc 180 ngày là quy ước của nhóm, không khẳng định mọi khách đều xem khoảng thời gian này là rời bỏ. Dữ liệu bán hàng lấy từ cửa hàng ở nước ngoài, đã dịch chuyển thời gian và quy đổi tiền tệ nên có thể khác hành vi khách hàng thực tế tại Việt Nam. Tương tác văn bản trong dự án được gắn nhân tạo theo hợp đồng TH2. Kết quả phụ thuộc vào số lượng và chất lượng dữ liệu, cần được nhân viên kiểm tra trước khi hành động.

## 8. Cách chạy lại

```powershell
python manage.py run_ai_pipeline --only churn
```

Sau khi chạy, lấy chỉ số, mã batch, phương pháp được chọn và phân bố mức rủi ro từ các dòng kết quả của batch đó rồi thay toàn bộ mục “Chưa có” ở trên bằng số liệu thực.
