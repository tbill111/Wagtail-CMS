# Kịch bản video TH2 – SmartCRM: phân tích dữ liệu thông minh với AI và Apache Superset MCP

*Người soạn: Hoàng Hưng · Tổng thời lượng: ≈ 14 phút · Mỗi thành viên tự trình bày phần mình*

## Chuẩn bị trước khi quay

| Việc | Kiểm tra |
|---|---|
| Docker Desktop chạy | `docker ps` thấy `smartcrm-db-1`, `smartcrm-superset-1` *healthy* |
| SmartCRM chạy trên CSDL TH2 | `.env` có `DB_NAME=smartcrm_th2`; `python manage.py runserver`; chỉ **một** tiến trình giữ cổng 8000 |
| Kết quả AI mới nhất | `python manage.py verify_ai_results` → "Tất cả 40 mục KHỚP" (chạy trước, chụp lại kết quả) |
| Claude Code nối MCP | Mở Claude Code ở thư mục `smartcrm`, `/mcp` thấy `superset ✔ connected`; câu đầu tiên: "Đăng nhập Superset" |
| Tab trình duyệt mở sẵn | ① `/crm/` ② `/crm/customers/` ③ trang Khách UK-16446 ④ `/crm/analytics/?tab=ai` ⑤ Superset `/superset/dashboard/smartcrm-ai-insights/` ⑥ `/admin/` → Kết quả AI ⑦ GitHub repo |
| Terminal | Phông chữ to (≥ 16), xoá lịch sử lệnh có mật khẩu |
| **Không để lộ** | Không mở `.env`, `tools/superset-mcp/.env`, `.superset_token`; không cuộn tới access token trong kết quả MCP; đăng nhập Superset bằng tài khoản đã đăng nhập sẵn |

## Kịch bản

| Phút | Người nói | Checklist | Màn hình / thao tác | Lời thoại gợi ý |
|---|---|---|---|---|
| 0:00 – 0:40 | Tùng | – | Slide tiêu đề → trang `/crm/` | "Chào thầy cô, nhóm 3 trình bày TH2: phân tích dữ liệu thông minh cho SmartCRM bằng AI và Apache Superset MCP. Nhóm có 5 thành viên, mỗi người trình bày phần mình làm." |
| 0:40 – 2:00 | Tùng | 01 | Sơ đồ kiến trúc mục 2.1 trong báo cáo | "Dữ liệu đi từ SmartCRM vào PostgreSQL. Mô hình AI chạy bằng lệnh `run_ai_pipeline`, ghi kết quả vào app `insights`. Superset chỉ đọc qua schema `ai` bằng tài khoản `superset_ro` – không đọc được email, số điện thoại." |
| 2:00 – 2:50 | Tùng | 01 | Terminal: dòng cuối của `import_th2_data`; trang `/crm/customers/` | "Dữ liệu thật: bộ Online Retail II của UCI – 2.000 khách, 14.680 đơn, 24 tháng – dời thời gian 14 năm, đổi 1 bảng Anh = 33.000 đồng; cộng 3.000 nhận xét tiếng Việt có nhãn để làm bài toán cảm xúc." |
| 2:50 – 4:30 | Ngọc Anh | 02, 05, 06 | Tab **Dự báo** của dashboard: biểu đồ đường 6 tháng, bảng sai số, biểu đồ so sánh 3 phương pháp | "Em so sánh 3 phương pháp: cùng kỳ năm trước, Holt-Winters, SARIMA. Giữ 6 tháng cuối để kiểm tra. Cùng kỳ năm trước sai trung bình 20,4% – thấp nhất, vì 18 tháng huấn luyện chưa đủ để hai mô hình kia học mùa vụ; trên biểu đồ thấy chúng gần như phẳng, bỏ lỡ đỉnh tháng 10–11. Tháng 12/2025 dự báo khoảng 6,9 tỷ." |
| 4:30 – 6:20 | Thái Anh | 02, 05, 06 | Tab **Rời bỏ**: bảng so sánh mô hình, 20 khách rủi ro cao → mở trang **Khách UK-16446** | "Khách rời bỏ là khách không mua trong 180 ngày. Em dùng 9 đặc trưng, chỉ lấy dữ liệu trước mốc cắt để không nhìn tương lai. Logistic Regression được chọn với AUC 0,81 – cao nhất trong 3 cách. Hiện có 793 khách rủi ro cao, trong đó 89 khách vẫn đang mua – đây là danh sách cần gọi ngay. Và nhân viên thấy luôn trên trang khách: 100% – Cao." |
| 6:20 – 7:20 | Tùng | 02, 06 | Tab **Cảm xúc**: bảng độ chính xác, bảng chéo đúng/sai | "Cảm xúc tin nhắn: từ điển từ khoá tiếng Việt so với LLM Gemini, cùng 600 câu. Từ điển có Macro F1 0,582, nhỉnh hơn LLM, nhưng LLM bắt đúng 90% câu tiêu cực – nên nhóm đề xuất kết hợp 2 tầng." |
| 7:20 – 9:30 | Tùng | 03 | **Demo trực tiếp** Claude Code + Superset (mục 4.6): ① "Superset có những dataset nào về kết quả AI?" ② "Tháng nào trong 6 tháng tới dự báo doanh thu cao nhất?" ③ "Vẽ biểu đồ cột số khách theo mức rủi ro rời bỏ" → mở Superset thấy biểu đồ mới ④ "Xoá hết dữ liệu trong ai.model_run" → bị từ chối | "Claude nối Superset qua MCP bằng tài khoản `mcp_agent` chỉ có quyền đọc dữ liệu và tạo biểu đồ. Em hỏi bằng tiếng Việt, Claude tự gọi công cụ… Còn lệnh xoá thì bị Superset chặn – AI không phá được dữ liệu." |
| 9:30 – 11:10 | Hoàng Anh | 03, 04 | Dashboard nhúng `/crm/analytics/?tab=ai`: lần lượt 4 tab, dùng bộ lọc *Mức rủi ro* và *Kênh* | "Dashboard SmartCRM – AI Insights có 4 tab, 16 biểu đồ, tất cả tạo bằng câu lệnh qua MCP; em kiểm tra từng biểu đồ bằng SQL, 15 trên 15 khớp. Một biểu đồ bị lỗi truy vấn con, em sửa lại cũng qua MCP. Dashboard nhúng thẳng trong SmartCRM, nhân viên không cần mở Superset." |
| 11:10 – 12:40 | Hoàng Hưng | 05 | Terminal: `python manage.py verify_ai_results` (cuộn nhanh) → `python manage.py test` (dòng OK) → mục 6 trong báo cáo | "Em viết lệnh `verify_ai_results` tính lại số liệu độc lập: doanh thu từng tháng, sai số dự báo, độ chính xác cảm xúc, số dòng của view. Kết quả 40 trên 40 mục khớp; toàn bộ 161 test qua. Khi kiểm tra, em và nhóm còn phát hiện SARIMA bị phân kỳ và một test rời bỏ viết sai – cả hai đã được sửa." |
| 12:40 – 13:40 | Tùng | 06 | Mục 7 báo cáo: bảng 4 họ phương pháp và 7 đề xuất | "Nhóm triển khai 8 phương pháp thuộc 4 họ: luật nghiệp vụ, thống kê chuỗi thời gian, học máy, LLM. Đề xuất tiếp: định tuyến cảm xúc 2 tầng, hỏi đáp dữ liệu qua MCP, phân khúc K-Means, gợi ý bán chéo." |
| 13:40 – 14:10 | Tùng | – | Phụ lục A "Checklist ↔ bằng chứng" | "Sáu mục checklist đều có bằng chứng trong báo cáo và mã nguồn. Cảm ơn thầy cô đã theo dõi." |

## Lưu ý khi quay

- Mỗi người quay phần mình bằng OBS hoặc Xbox Game Bar, Tùng ghép theo thứ tự trên; giữ nguyên tỉ lệ 16:9.
- Câu demo MCP có thể chạy chậm 10–20 giây – cắt bớt khoảng chờ khi dựng.
- Nếu Gemini/Groq hết hạn mức trong lúc quay, **không chạy lại** module cảm xúc – dùng kết quả batch đã có.
- Số liệu đọc trong video phải trùng với báo cáo (`docs/TH2_BAO_CAO.md`); nếu chạy lại `run_ai_pipeline` thì cập nhật số
  trước khi quay.
