# Dự đoán khách hàng rời bỏ

*Người viết: Thái Anh · Code: `insights/pipeline/churn.py`, hiển thị: `crm/templates/crm/_churn_risk.html`, `insights/display.py` · Batch: **20261017-072049***

## 1. Bài toán và câu hỏi kinh doanh

Module ước tính khách hàng nào có nguy cơ không quay lại mua hàng trong 180 ngày tiếp theo. Nhân viên chăm sóc khách hàng có thể ưu tiên liên hệ nhóm rủi ro cao, kiểm tra trải nghiệm gần đây và đề xuất hỗ trợ phù hợp. Điểm rủi ro là tín hiệu tham khảo, không tự động đổi trạng thái khách hàng.

## 2. Dữ liệu

Nguồn bán hàng theo hợp đồng TH2 là Online Retail II, lấy mẫu 2.000 khách có mã khách, dời thời gian thêm 14 năm và quy đổi theo tỷ giá cố định 33.000 VNĐ/GBP. Theo số liệu nạp ghi trong [báo cáo kiến trúc](01_kien_truc.md), dữ liệu hiện có 14.680 đơn (2.370 đơn huỷ), 255.715 dòng sản phẩm và 4.424 sản phẩm; thời gian giao dịch từ 01/12/2023 đến 09/12/2025. Có 24 tháng trọn vẹn từ 12/2023 đến 11/2025. Ngày tham chiếu là **09/12/2025**. Báo cáo kiến trúc ghi nhận 805 khách có trạng thái CRM “Đã rời bỏ”; con số này là trạng thái nghiệp vụ, không thay thế số nhãn churn của tập huấn luyện.

Cutoff bằng ngày tham chiếu trừ 180 ngày. Tập huấn luyện gồm khách có ít nhất một đơn hoàn thành trước cutoff. Nhãn bằng 1 nếu khách không có đơn hoàn thành trong khoảng `(cutoff, ngày tham chiếu]`, bằng 0 nếu có. Đặc trưng chỉ tính từ dữ liệu **đến hết ngày cutoff** (12/06/2025), nhãn xét các đơn **sau ngày cutoff** đến hết 09/12/2025 – mỗi đơn thuộc đúng một phía, không nhìn trước tương lai. Tập có nhãn gồm **1.690 khách**, trong đó **807 khách rời bỏ (47,75%)** – hai lớp gần cân bằng. Sau khi chọn mô hình, điểm rủi ro được chấm cho **2.000 khách** có ít nhất một đơn hoàn thành đến ngày tham chiếu.

## 3. Phương pháp

- **Luật RFM (`rfm_rule`):** dùng thứ hạng phần trăm của `recency_days`; khách càng lâu chưa mua thì điểm càng cao. Đây là quy tắc không huấn luyện mô hình.
- **Logistic Regression – hồi quy logistic (`logistic_regression`):** chuẩn hoá đặc trưng bằng `StandardScaler`, dùng `class_weight="balanced"` và `max_iter=1000`.
- **Random Forest – rừng ngẫu nhiên (`random_forest`):** dùng 300 cây, `class_weight="balanced"` và `random_state=42`. Năm đặc trưng quan trọng nhất sẽ được ghi trong kết quả batch.

Cả ba phương pháp dùng các đặc trưng recency, frequency, monetary, average order value, tenure, số đơn 90 ngày gần nhất, số đơn huỷ, số sản phẩm khác nhau và số tương tác.

## 4. Cách đánh giá

Dữ liệu được chia ngẫu nhiên thành 70% huấn luyện và 30% kiểm tra, phân tầng theo nhãn, `random_state=42`. AUC đo khả năng xếp khách có nguy cơ cao hơn khách không rời bỏ; 0,5 tương đương đoán ngẫu nhiên, 1 là phân biệt hoàn hảo. Precision trả lời: trong số khách mô hình báo có nguy cơ, bao nhiêu phần trăm thật sự rời bỏ. Recall trả lời: trong số khách thật sự rời bỏ, mô hình phát hiện được bao nhiêu phần trăm. Precision, recall, F1 và accuracy dùng ngưỡng xác suất 0,5. Phương pháp có AUC cao nhất được chọn.

## 5. Kết quả

Mã batch: **`20261017-072049`** (số lấy từ `ai.model_run`). Tập huấn luyện 1.183 khách, tập kiểm tra 507 khách.

| Phương pháp | AUC | Precision | Recall | F1 | Accuracy | n_train | n_test |
|---|---:|---:|---:|---:|---:|---:|---:|
| Luật RFM | 0,768 | 66,9% | 70,3% | 0,686 | 69,2% | 1.183 | 507 |
| **Logistic Regression ★** | **0,810** | **69,7%** | 75,2% | **0,724** | **72,6%** | 1.183 | 507 |
| Random Forest | 0,782 | 67,3% | **76,4%** | 0,716 | 71,0% | 1.183 | 507 |

- **Tỷ lệ rời bỏ của tập:** 47,73% (`churn_rate` trên toàn bộ 1.690 khách có nhãn).
- **Ma trận nhầm lẫn của phương pháp được chọn – Logistic Regression** (hàng = nhãn thật, cột = dự đoán, 507 khách kiểm tra):

  |  | Dự đoán không rời bỏ | Dự đoán rời bỏ |
  |---|---:|---:|
  | Thật sự không rời bỏ | 186 (tn) | 79 (fp – gọi nhầm) |
  | Thật sự rời bỏ | 60 (fn – bỏ sót) | 182 (tp) |

- **Top đặc trưng quan trọng của Random Forest:** `recency_days` 0,209 · `monetary` 0,167 · `distinct_products` 0,139 · `avg_order_value` 0,121 · `tenure_days` 0,120.
- **Số khách theo mức rủi ro (Logistic Regression, 2.000 khách):** Cao **793** · Trung bình **484** · Thấp **723**.
- **Trang khách:** ví dụ Khách UK-16446 hiện "100% – Cao · Mô hình Logistic Regression".

## 6. Kết luận

Chọn **Logistic Regression** vì có AUC cao nhất (0,810), đồng thời F1 và accuracy cũng cao nhất. Ba phương pháp chênh nhau không nhiều (AUC 0,77 – 0,81) vì tín hiệu mạnh nhất là *bao lâu rồi khách chưa mua* – luật RFM chỉ dựa vào recency cũng đạt 0,768. Random Forest có recall cao nhất (bắt được 76% khách rời bỏ thật) – phù hợp nếu cửa hàng chấp nhận gọi nhầm nhiều hơn để không bỏ sót.

Gợi ý cho nhân viên: ưu tiên rà soát nhóm rủi ro cao (793 khách), trước hết là khách có tổng chi tiêu lớn; xem lịch sử mua hàng và tương tác, sau đó liên hệ để hỏi nhu cầu hoặc xử lý vấn đề còn tồn đọng. Nhóm trung bình có thể nhận email nhắc sản phẩm từng mua. Không gửi cùng một nội dung tự động cho mọi khách.

## 7. Hạn chế

Mốc 180 ngày là quy ước của nhóm, không khẳng định mọi khách đều xem khoảng thời gian này là rời bỏ. Dữ liệu bán hàng lấy từ cửa hàng ở nước ngoài, đã dịch chuyển thời gian và quy đổi tiền tệ nên có thể khác hành vi khách hàng thực tế tại Việt Nam. Tương tác văn bản trong dự án được gắn nhân tạo theo hợp đồng TH2. Kết quả phụ thuộc vào số lượng và chất lượng dữ liệu, cần được nhân viên kiểm tra trước khi hành động.

## 8. Cách chạy lại

```powershell
python manage.py run_ai_pipeline --only churn
```

Sau khi chạy, cập nhật bảng ở mục 5 bằng số của batch mới (lấy từ `ai.model_run`). Kiểm tra nhanh: `python manage.py test insights.tests.test_churn`.
