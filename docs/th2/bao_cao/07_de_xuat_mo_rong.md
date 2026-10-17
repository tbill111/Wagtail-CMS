# 7. Đề xuất mô hình và phương pháp AI khác (checklist 06 – cộng điểm sáng tạo)

*Người viết: Tùng*

## 7.1. Các họ phương pháp nhóm đã triển khai

Nhóm không dừng ở một mô hình mà triển khai **3 bài toán × 2–3 phương pháp = 8 phương pháp**, thuộc **4 họ phương pháp AI
khác nhau**, cộng thêm 2 tính năng LLM có sẵn trong SmartCRM:

| Họ phương pháp | Phương pháp | Bài toán | Đặc điểm |
|---|---|---|---|
| **Luật nghiệp vụ** (rule-based) | Cùng kỳ năm trước | Dự báo doanh thu | Mốc so sánh tối thiểu, ai cũng hiểu |
| | Luật RFM | Khách rời bỏ | Dựa trên kinh nghiệm bán hàng: lâu không mua thì dễ rời bỏ |
| | Từ điển từ khoá tiếng Việt | Cảm xúc | Không cần dữ liệu huấn luyện, miễn phí, < 1 ms/câu, giải thích được |
| **Thống kê chuỗi thời gian** | Holt-Winters | Dự báo doanh thu | Tách xu hướng và mùa vụ |
| | SARIMA | Dự báo doanh thu | Mô hình tự hồi quy có mùa vụ, có khoảng tin cậy |
| **Học máy có giám sát** | Logistic Regression | Khách rời bỏ | Ra xác suất, giải thích được qua hệ số |
| | Random Forest | Khách rời bỏ | Bắt được quan hệ phi tuyến, có độ quan trọng đặc trưng |
| **Mô hình ngôn ngữ lớn (LLM)** | Gemini (+ AI dự phòng Groq) | Cảm xúc | Hiểu ngữ cảnh, câu khen chê lẫn lộn; tốn hạn mức, ≈ 1 giây/câu |
| | *Có sẵn trong SmartCRM:* phân loại khách | Cảm xúc, mức ưu tiên, trạng thái đề xuất cho từng khách | Dùng tại trang chi tiết khách |
| | *Có sẵn trong SmartCRM:* báo cáo nhận định | Tóm tắt tình hình kinh doanh | Dùng tại trang Báo cáo AI |

Mỗi bài toán có **một phương pháp đơn giản làm mốc** và đánh giá trên **cùng tập kiểm tra**, nên chênh lệch giữa các phương
pháp là so sánh công bằng (mục 3). Kết quả so sánh thực tế (dự báo, rời bỏ: batch `20261017-072049`; cảm xúc:
`20261014-215419`):

| Bài toán | Phương pháp được chọn | Chỉ số | Nhận xét |
|---|---|---|---|
| Dự báo doanh thu | **Cùng kỳ năm trước** (luật) | MAPE 20,4% (SARIMA 29,4%, Holt-Winters 29,8%) | Chuỗi 24 tháng quá ngắn để mô hình thống kê học mùa vụ – mốc đơn giản thắng |
| Khách rời bỏ | **Logistic Regression** (học máy) | AUC 0,810 (Random Forest 0,782, Luật RFM 0,768) | Học máy hơn luật RFM không nhiều – tín hiệu chính là thời gian từ lần mua cuối |
| Cảm xúc | **Từ điển từ khoá** (luật) | Macro F1 0,582 (LLM 0,575) | LLM bắt câu tiêu cực tốt hơn hẳn (129/144 = 89,6% so với 82/144 = 56,9%) – cơ sở của đề xuất #6 |

Bài học chung: **phương pháp phức tạp chỉ đáng dùng khi thắng được mốc đơn giản trên cùng tập kiểm tra** – nhóm giữ
nguyên nguyên tắc chọn theo chỉ số, kể cả khi mốc đơn giản thắng.

## 7.2. Đề xuất mở rộng (chưa triển khai)

| # | Đề xuất | Mục đích kinh doanh | Dữ liệu cần | Phương pháp | Cách đánh giá | Độ khó |
|---|---|---|---|---|---|---|
| 1 | **Phân khúc khách bằng K-Means** | Tìm nhóm khách có hành vi giống nhau mà luật RFM chia cứng không thấy, để thiết kế ưu đãi riêng | Recency, frequency, monetary, giá trị đơn TB, số nhóm hàng đã mua (đã có trong module rời bỏ) | Chuẩn hoá đặc trưng, K-Means, chọn số cụm bằng Elbow / Silhouette | Silhouette score; so với phân khúc RFM; đặt tên và đọc ý nghĩa từng cụm | Thấp |
| 2 | **Phát hiện bất thường doanh thu** | Cảnh báo sớm ngày doanh thu tụt hoặc tăng đột biến (lỗi hệ thống, đơn gian lận, khuyến mãi hiệu quả) | Doanh thu theo ngày | Isolation Forest; hoặc so với khoảng tin cậy của mô hình dự báo | Gắn nhãn tay một số ngày bất thường đã biết (lễ, Tết); precision / recall | Trung bình |
| 3 | **Gợi ý bán chéo** | "Khách mua A thường mua thêm B" để gợi ý khi lên đơn, tăng giá trị đơn | Dòng sản phẩm trong từng đơn (255.715 dòng sẵn có) | Luật kết hợp Apriori / FP-Growth (support, confidence, lift) | Giữ lại các đơn gần nhất, đo tỉ lệ đơn có món được gợi ý (hit rate) | Trung bình |
| 4 | **LLM gợi ý hành động cho khách rủi ro cao** | Biến xác suất rời bỏ thành việc cụ thể cho nhân viên (gọi điện, tặng mã giảm giá…) | Điểm rời bỏ, lịch sử mua, cảm xúc tin nhắn gần nhất | Gọi LLM với ngữ cảnh khách (dùng lại `GeminiCRMService.build_customer_context`) | Nhân viên chấm 1–5 mức hữu ích; theo dõi tỉ lệ khách được chăm sóc quay lại mua | Thấp |
| 5 | **Hỏi đáp dữ liệu bằng tiếng Việt qua MCP** | Quản lý hỏi "tháng tới doanh thu bao nhiêu?", "khách nào sắp bỏ đi?" mà không cần biết SQL | Các view `ai.*`, `analytics.*` (đã có) | LLM + Superset MCP: sinh SQL đọc, chạy qua tài khoản chỉ đọc, trả lời bằng lời | Bộ 30 câu hỏi mẫu có đáp án; tỉ lệ trả lời đúng số liệu | Thấp (hạ tầng đã có, xem mục 4) |
| 6 | **Định tuyến cảm xúc 2 tầng** | Giảm chi phí LLM mà vẫn bắt được khách không hài lòng | Kết quả hai phương pháp cảm xúc hiện có | Từ điển chấm mọi câu; chỉ câu "tiêu cực/trung lập" mới gửi LLM | Macro F1 và số lượt gọi LLM so với dùng LLM cho tất cả (ước tính giảm ≈ 55% lượt gọi) | Thấp |
| 7 | **Mô hình cảm xúc tiếng Việt chuyên biệt (PhoBERT)** | Độ chính xác cao hơn từ điển, không tốn hạn mức như LLM | 10.010 nhận xét có nhãn (đã tải) | Tinh chỉnh `vinai/phobert-base` trên tập huấn luyện | Macro F1 trên đúng tập 600 câu hiện tại | Cao (cần GPU) |

## 7.3. Thứ tự đề xuất nếu phát triển tiếp

1. **#6 Định tuyến 2 tầng** và **#5 Hỏi đáp qua MCP** – tận dụng ngay những gì đã có, chi phí thấp, giá trị thấy rõ.
2. **#1 K-Means** – dùng lại đặc trưng của module rời bỏ, làm giàu tab Rời bỏ trên dashboard.
3. **#3 Bán chéo**, **#4 LLM gợi ý hành động** – nối kết quả phân tích vào thao tác bán hàng hằng ngày trên SmartCRM.
4. **#2 Bất thường**, **#7 PhoBERT** – cần thêm dữ liệu gán nhãn hoặc phần cứng.
