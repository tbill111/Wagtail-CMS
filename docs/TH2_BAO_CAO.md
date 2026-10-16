# Báo cáo Tổng kết Dự án SmartCRM (Wagtail CMS + AI Gemini)

**Nhóm thực hiện:** Nhóm 3  
**Môn học:** Hệ thống kinh doanh thông minh

## 1. Giới thiệu dự án
SmartCRM là hệ thống quản trị quan hệ khách hàng được xây dựng trên nền tảng Wagtail CMS, tích hợp trực tiếp trợ lý AI Google Gemini. Hệ thống tự động hóa các tác vụ chăm sóc khách hàng bao gồm: phân loại cảm xúc từ lịch sử tương tác, tự động soạn thảo email phản hồi, và tổng hợp báo cáo nhận định rủi ro kinh doanh.

## 2. Bảng Đối chiếu Checklist và Bằng chứng (Nhiệm vụ Tuần 4)

| STT | Hạng mục Checklist | Người phụ trách | Trạng thái | Bằng chứng (File/Link/Ảnh) |
|---|---|---|---|---|
| 1 | Cài đặt môi trường, Wagtail, SQLite, `.env` | Thành viên 1 | Hoàn thành | `README.md`, file `requirements.txt` |
| 2 | Model CSDL (Customer, Order, AIReport) | Thành viên 1 & 2 | Hoàn thành | `crm/models.py`, các file migration |
| 3 | Tích hợp AI: Gợi ý phản hồi Email | Thành viên 1 | Hoàn thành | `crm/services/gemini_service.py` |
| 4 | Tích hợp AI: Phân loại cảm xúc & Rủi ro | Thành viên 2 | Đang sửa | `ui_customer_list_missing_ai.png` |
| 5 | Tích hợp AI: Báo cáo nhận định | Thành viên 2 | Hoàn thành | Ảnh chụp màn hình Tab Báo Cáo AI |
| 6 | Kiểm thử tự động chỉ đọc (`verify_ai_results`) | Hoàng Hưng | Hoàn thành | `crm/management/commands/verify_ai_results.py` |
| 7 | Báo cáo đối chiếu Dashboard & SQL | Hoàng Hưng | Hoàn thành | `docs/08_kiem_thu_doi_chieu.md` |
| 8 | Dashboard Apache Superset (Docker) | Cả nhóm | Hoàn thành | `docs/TH1_SUPERSET.md` |

## 3. Tóm tắt Kết quả Kiểm thử Hệ thống (Bởi Hoàng Hưng)
Quá trình chạy lệnh kiểm thử tự động `verify_ai_results` trên tập dữ liệu Mock Data (10 khách hàng, 20 đơn hàng) đã phát hiện các vấn đề cần khắc phục ở Backend:
*   **Lỗi Schema Model:** Thiếu trường `risk_score` trong bảng `Customer`. Giao diện danh sách khách hàng chưa hiển thị cột điểm rủi ro.
*   **Lệch số liệu doanh thu:** Doanh thu dự báo sinh ra ngẫu nhiên trong bảng `AIReport` (ví dụ: 23,025,240 VNĐ) không khớp với tổng doanh thu thực tế được cộng gộp từ bảng `Order` (79,900,000 VNĐ).
*   **Module phân loại AI:** Cột "Ưu tiên AI" trên frontend hiện đang trống (—), cần chạy lại batch xử lý AI cho khách hàng.

*Đề xuất:* Đội Backend bổ sung cột `risk_score`, chạy lại lệnh `makemigrations` và điều chỉnh logic để AIReport lấy đúng tổng `total_amount` từ Order trước khi dự báo.
