# 3.3. Mô hình phân tích cảm xúc tin nhắn khách hàng (checklist 02, 06)

*Người viết: Tùng · Code: `insights/pipeline/sentiment.py`, `insights/pipeline/lexicon_vi.py` · Batch: **20261014-215419***

## 1. Bài toán và câu hỏi kinh doanh

*Khách đang hài lòng hay bực bội? Kênh nào, tháng nào nhiều phản hồi tiêu cực?* Mỗi tin nhắn / nhận xét của khách được
gán một nhãn **Tích cực / Trung lập / Tiêu cực**. Nhân viên chăm sóc dùng kết quả để ưu tiên xử lý khách đang không hài
lòng; quản lý theo dõi xu hướng cảm xúc theo kênh và theo thời gian trên dashboard.

## 2. Dữ liệu

| Hạng mục | Giá trị |
|---|---|
| Nguồn | 3.000 nhận xét điện thoại tiếng Việt (Hugging Face `anotherpolarbear/vietnamese-sentiment-analysis`, MIT), nạp thành *Lịch sử tương tác* |
| Nhãn đúng | Từ số sao người viết tự chấm: 1–2 sao = Tiêu cực, 3 = Trung lập, 4–5 = Tích cực |
| Tập đánh giá | **600 câu**, lấy mẫu phân tầng theo nhãn (`random_state=42`): 380 tích cực, 144 tiêu cực, 76 trung lập |
| Lý do lấy mẫu | Giới hạn số lượt gọi LLM miễn phí; **cả hai phương pháp chấm đúng cùng 600 câu** để so sánh công bằng |

## 3. Phương pháp

| Phương pháp | Mô tả | Tham số chính |
|---|---|---|
| **Từ điển từ khoá** (`keyword`) | Chuẩn hoá chữ thường, bỏ dấu câu, tách từ; so khớp **tham lam cụm dài trước** ("nhanh hết pin" trước "nhanh") với 73 cụm tích cực và 72 cụm tiêu cực (có cả từ viết tắt: ok, ko, lag…). Từ phủ định ("không", "chưa", "ko"…) đứng trước tối đa 2 từ thì **đảo chiều** cụm sau ("không lag" → tích cực). Điểm = số cụm tích cực − tiêu cực; khen chê ngang nhau → trung lập | 73 / 72 cụm, 11 từ phủ định, cửa sổ phủ định 2 từ |
| **LLM** (`gemini`) | Gọi mô hình ngôn ngữ lớn qua dịch vụ AI sẵn có của SmartCRM (`GeminiCRMService`): Gemini, tự chuyển sang **AI dự phòng Groq (GPT-OSS 120B)** khi Gemini lỗi hoặc hết hạn mức. Gửi theo lô 20 câu, yêu cầu trả JSON có schema `{id, label, confidence}`, `temperature = 0` để kết quả ổn định. Câu AI không trả lời được tính là trung lập | `gemini-3.8-flash`, dự phòng Groq, 30 lượt gọi, lô 20 câu |

## 4. Cách đánh giá

- So nhãn dự đoán với nhãn đúng trên 600 câu.
- **Accuracy** – tỉ lệ câu đoán đúng.
- **Macro F1** – trung bình F1 của 3 nhãn, **mỗi nhãn nặng như nhau**. Chọn chỉ số này vì dữ liệu lệch (63% tích cực): một
  mô hình đoán "tích cực" cho mọi câu đã đạt accuracy 63% nhưng macro F1 rất thấp.
- **F1 / Precision / Recall từng nhãn** và **ma trận nhầm lẫn** – xem mô hình hay nhầm ở đâu.
- **Thời gian xử lý mỗi câu** và **chi phí / hạn mức** – yếu tố triển khai thực tế.

## 5. Kết quả

| Phương pháp | Accuracy | **Macro F1** | F1 Tích cực | F1 Trung lập | F1 Tiêu cực | Thời gian / câu |
|---|---|---|---|---|---|---|
| Từ điển từ khoá ★ | **0,688** | **0,582** | **0,844** | **0,293** | 0,610 | < 1 ms |
| LLM (Gemini + AI dự phòng) | 0,667 | 0,575 | 0,785 | 0,220 | **0,719** | ≈ 1.096 ms |

★ = phương pháp được chọn (`is_selected`, macro F1 cao nhất).

**Ma trận nhầm lẫn** (hàng = nhãn đúng, cột = nhãn dự đoán):

| Từ điển | → Tích cực | → Trung lập | → Tiêu cực | Recall |
|---|---|---|---|---|
| Tích cực (380) | **298** | 67 | 15 | 78,4% |
| Trung lập (76) | 15 | **33** | 28 | 43,4% |
| Tiêu cực (144) | 13 | 49 | **82** | 56,9% |
| *Precision* | *91,4%* | *22,1%* | *65,6%* | |

| LLM | → Tích cực | → Trung lập | → Tiêu cực | Recall |
|---|---|---|---|---|
| Tích cực (380) | **248** | 99 | 33 | 65,3% |
| Trung lập (76) | 0 | **23** | 53 | 30,3% |
| Tiêu cực (144) | 4 | 11 | **129** | **89,6%** |
| *Precision* | *98,4%* | *17,3%* | *60,0%* | |

## 6. Kết luận

- **Tổng thể hai phương pháp ngang nhau** (macro F1 0,582 so với 0,575); từ điển được chọn theo quy tắc chỉ số cao nhất.
- **LLM bắt khách không hài lòng tốt hơn hẳn:** nhận ra **129/144 = 89,6%** nhận xét tiêu cực, từ điển chỉ 56,9%. Khi một tin
  nhắn được LLM gắn "tích cực" thì gần như chắc chắn đúng (precision 98,4%).
- **Từ điển nhanh và miễn phí** (dưới 1 ms/câu, không gọi mạng), phù hợp chấm toàn bộ tin nhắn hằng ngày.
- **Đề xuất triển khai:** dùng từ điển chấm mọi tin nhắn; tin nhắn từ điển chấm "tiêu cực" hoặc "trung lập" thì gửi thêm cho
  LLM xác nhận – giữ ưu điểm bắt tiêu cực của LLM mà giảm khoảng 55% số lượt gọi.

## 7. Hạn chế

- **Nhãn từ số sao có nhiễu:** nhiều nhận xét 4–5 sao vẫn chứa than phiền ("máy mượt nhưng pin tụt nhanh"). LLM đọc nội dung
  nên xếp các câu này vào trung lập / tiêu cực – bị tính là sai dù hợp lý. Đọc thử 15 trong 99 câu "4–5 sao" bị LLM xếp
  trung lập: **14 câu là khen kèm chê hoặc câu hỏi** (ví dụ *"máy oke, nhưng cần khắc phục lỗi pin dưới 10% không cho bật
  đèn flash"*, *"Cho hỏi là đt mình xài đc 8 tháng rồi… pin còn 87% là sao vậy ad"*), chỉ 1 câu khen trọn vẹn. Nghĩa là
  độ chính xác thật của LLM cao hơn con số đo được.
- **Lớp trung lập khó và ít mẫu** (76 câu): cả hai phương pháp đều yếu (F1 0,22–0,29).
- **Hạn mức miễn phí:** trong lần chạy này Gemini báo **hết hạn mức (quota)**, phần lớn các lô do **Groq** trả lời, Groq cũng có
  lúc báo 429 nên phải chờ và thử lại – tổng thời gian chạy khoảng 11 phút cho 600 câu. Kết quả LLM vì vậy là của **Gemini kết
  hợp Groq**, chưa tách được riêng từng mô hình. Từ lần chạy sau, `params.batches_by_provider` ghi số lô mỗi nhà cung cấp trả
  lời; nên chạy lại khi hạn mức Gemini được làm mới để có số liệu riêng của Gemini.
- **Văn bản gắn nhân tạo:** nhận xét là của một bộ dữ liệu điện thoại, được gắn ngẫu nhiên cho khách của cửa hàng Online
  Retail II. Biểu đồ cảm xúc theo kênh / theo khách chỉ mang tính minh hoạ; độ chính xác mô hình thì vẫn đúng vì so với nhãn thật.
- **Từ điển tự xây dựng**, chưa phủ hết từ lóng, lỗi chính tả, câu mỉa mai.

## 8. Cách chạy lại

```powershell
python manage.py run_ai_pipeline --only sentiment          # 600 câu, cả hai phương pháp
$env:SENTIMENT_SAMPLE = "0"; python manage.py run_ai_pipeline --only sentiment   # chấm hết 3.000 câu (tốn hạn mức)
python manage.py test insights.tests.test_sentiment
```
