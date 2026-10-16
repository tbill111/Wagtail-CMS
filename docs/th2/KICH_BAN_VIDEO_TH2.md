# Kịch bản Video Demo SmartCRM TH2 (Thời lượng: 12-15 phút)

*Phân công: Cả nhóm chia sẻ màn hình qua Zoom, mỗi người nói 1 phần theo đúng luồng Data của TH2.*

**Phút 01-03 | Bạn A: Kiến trúc & Database TH2**
*   **Screencast:** Mở pgAdmin hoặc DBeaver chiếu Database `smartcrm_th2`.
*   **Voiceover:** "Xin chào, nhóm chúng em xin trình bày TH2 của hệ thống SmartCRM. Khác với TH1, TH2 sử dụng PostgreSQL làm Data Warehouse, chia tách rõ app `crm` (nghiệp vụ) và app `insights` (phân tích AI). Đây là các bảng ModelRun, RevenueForecast, ChurnScore..."

**Phút 03-06 | Bạn B: AI Batch Processing (Dự báo & Rời bỏ)**
*   **Screencast:** Chạy lệnh trigger AI Batch. Chiếu bảng dữ liệu cập nhật probability [0,1].
*   **Voiceover:** "Các module AI hoạt động theo lô (batch). Ở module Churn, AI chấm điểm xác suất rời bỏ từ 0-1. Tại module Revenue, hệ thống dự báo doanh thu kèm dải lower và upper bound. Mỗi lần chạy được lưu vết trong ModelRun với `is_selected=True` cho cách tốt nhất."

**Phút 06-09 | Bạn C: Phân tích Cảm xúc & MCP**
*   **Screencast:** Mở tính năng Chatbot gọi MCP.
*   **Voiceover:** "Đặc biệt ở TH2, hệ thống sử dụng Model Context Protocol (MCP). Agent không cần gọi API rời rạc mà có thể chủ động query trực tiếp vào SQL một cách bảo mật để đánh giá chính xác độ đo Macro F1 và Accuracy của các tương tác khách hàng."

**Phút 09-12 | Bạn D: Apache Superset Dashboard**
*   **Screencast:** Mở trình duyệt Superset (cổng 8088), chiếu dashboard doanh thu và biểu đồ rủi ro.
*   **Voiceover:** "Tất cả các metrics từ app `insights` được đổ về Superset. Tại đây, giám đốc có thể quan sát biểu đồ Real-time giữa Actual và Forecast, hoặc xem phân bổ tập khách hàng có nguy cơ rời bỏ > 0.7."

**Phút 12-15 | Hoàng Hưng: Tự động hóa Kiểm thử (QA)**
*   **Screencast:** Chạy `python manage.py test insights` (hiện OK). Chạy lệnh `python manage.py verify_ai_results`.
*   **Voiceover:** "Để đảm bảo số liệu AI sinh ra là chính xác, em đã viết tập lệnh Test và Command đối chiếu. Lệnh sẽ quét trực tiếp ModelRun lấy batch mới nhất, tính toán lại doanh thu xem có lọt vào dải upper-lower không, kiểm tra xác suất rời bỏ. Nếu phát hiện lệch, hệ thống lập tức Raise CommandError (Mã 1). Hiện tại toàn bộ hệ thống đều KHỚP."
