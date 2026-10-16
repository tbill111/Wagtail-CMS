# Kịch bản Video Demo SmartCRM (Thời lượng dự kiến: 12 - 15 phút)

**Yêu cầu khi quay:** Cả nhóm dùng Google Meet/Zoom, chia sẻ toàn màn hình. Đến phần của AI, người đó tự bật mic đọc lời thoại và thao tác chuột.

---

### Phút 0:00 - 2:00 | Thành viên 1 (Tùng/Trưởng nhóm) - Giới thiệu & Kiến trúc
*   **Hành động (Screencast):** Chiếu slide giới thiệu dự án hoặc mở file README.md, sau đó mở file `models.py` lướt qua cấu trúc bảng.
*   **Lời thoại:** "Chào thầy và các bạn, đại diện Nhóm 3 em xin trình bày dự án SmartCRM tích hợp AI Gemini trên nền tảng Wagtail CMS. Mục tiêu dự án là tự động hóa khâu chăm sóc khách hàng. Dữ liệu chạy trên SQLite, bao gồm các bảng chính: Customer, Order, InteractionLog và AIReport. Tụi em sử dụng SDK `google-genai` mới nhất để gọi API."

### Phút 2:00 - 5:00 | Thành viên 1 - Demo AI Gợi ý Email
*   **Hành động:** Mở giao diện `http://127.0.0.1:8000/crm/customers/`, bấm vào một khách hàng. Bấm nút "Gợi ý email AI", chọn giọng văn "Chuyên nghiệp".
*   **Lời thoại:** "Đây là tính năng đầu tiên: Trợ lý AI sinh email phản hồi. Khi bấm nút, hệ thống sẽ gom thông tin mua hàng, tổng chi tiêu và lịch sử của khách này thành Context gửi lên Gemini. Như mọi người thấy, AI đã tự viết một email cảm ơn rất cá nhân hóa dựa trên đúng mặt hàng khách vừa mua."

### Phút 5:00 - 8:00 | Thành viên 2 - Demo AI Phân loại & Báo cáo
*   **Hành động:** Mở Tab "Báo cáo nhận định AI". Chạy demo tính năng phân loại khách hàng, hiển thị các nhãn (Tích cực/Tiêu cực, Ưu tiên Cao/Thấp).
*   **Lời thoại:** "Tiếp theo là phần xử lý ngôn ngữ tự nhiên. Khi có Interaction Log mới, hệ thống tự động gọi AI phân tích cảm xúc và gán độ ưu tiên. Đồng thời, tính năng Báo cáo nhận định sẽ tổng hợp số liệu tuần qua, phân tích rủi ro kinh doanh và đưa ra đề xuất hành động cụ thể để team Sale nắm bắt."

### Phút 8:00 - 11:00 | Thành viên 3 & 4 - Database, Superset Dashboard
*   **Hành động:** Mở Terminal chiếu file `docker-compose.yml`, mở trình duyệt vào cổng `8088` (Superset) chiếu các biểu đồ thống kê.
*   **Lời thoại:** "Để trực quan hóa dữ liệu lớn, tụi em tích hợp Apache Superset qua Docker. Dữ liệu từ CRM được đẩy sang tầng view Analytics. Trên Dashboard này, quản lý có thể xem realtime biểu đồ doanh thu, tỷ lệ khách hàng rời bỏ và hiệu suất của từng chiến dịch một cách trực quan nhất mà không cần vào sâu hệ thống Wagtail."

### Phút 11:00 - 14:00 | Hoàng Hưng - Kiểm thử tự động & Tổng kết
*   **Hành động:** Mở VS Code chiếu file `verify_ai_results.py` và file `08_kiem_thu_doi_chieu.md`. Mở terminal gõ lệnh `python manage.py verify_ai_results` cho chạy ra lỗi.
*   **Lời thoại:** "Cuối cùng, ở vai trò QA, em đã phát triển một Custom Command trong Django tên là `verify_ai_results` để kiểm thử chéo kết quả của AI sinh ra với truy vấn SQL thực tế. Lệnh này hoạt động hoàn toàn ở chế độ Read-only. Quá trình kiểm tra trên dữ liệu thật đã bắt được lỗi lệch doanh thu dự báo và thiếu trường `risk_score` trong CSDL, em đã lập bảng đối chiếu chi tiết trong tài liệu Markdown và báo lại cho đội Dev. Dự án đáp ứng tốt các nghiệp vụ cơ bản, cảm ơn thầy và các bạn đã theo dõi!"
