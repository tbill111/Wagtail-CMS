# Prompt TH2 – Hoàng Anh: Dashboard "SmartCRM – AI Insights"

> **Cách dùng:** 2 giai đoạn. Giai đoạn 1 làm ngay khi Tùng gộp giai đoạn A (dashboard dựng trên **dữ liệu giả**).
> Giai đoạn 2 làm khi Tùng báo đã có kết quả mô hình thật. Mở Claude Code tại thư mục `smartcrm/`, dán từng khối.
> Phần này **không sửa code của SmartCRM**: agent làm việc với Superset qua MCP và viết tài liệu.

---

## GIAI ĐOẠN 1 – Cài đặt và dựng dashboard trên dữ liệu giả (tuần 1–2)

```text
Bạn là trợ lý phân tích dữ liệu, thành thạo Apache Superset, làm việc trong repo SmartCRM. Tôi là Hoàng Anh, thành viên
nhóm TH2 "Hệ thống phân tích dữ liệu thông minh tích hợp AI và Apache Superset". Phần của tôi: dựng dashboard
"SmartCRM – AI Insights" trên Superset, ưu tiên dùng Superset MCP (checklist 03, 04). Tôi mới học, hãy giải thích từng
bước ngắn gọn bằng tiếng Việt, mỗi khi cần tôi tự thao tác thì ghi rõ bấm vào đâu.

BƯỚC 0 – ĐỌC VÀ KIỂM TRA (bắt buộc):
- Đọc HẾT docs/th2/HOP_DONG_DU_LIEU.md (đặc biệt mục 7 view ai.* và mục 8 quy ước dashboard), docs/th2/CAI_DAT.md,
  docs/th2/CAI_DAT_MCP.md.
- Hướng dẫn tôi làm theo CAI_DAT.md trên máy tôi tới khi: Superset mở được, có kết nối "SmartCRM TH2 (chỉ đọc)", có 4
  dataset ai.*, đã chạy `python manage.py seed_ai_demo`. Kiểm tra từng điều kiện, cái nào chưa đạt thì chỉ tôi cách sửa.
  Nếu tài liệu sai/thiếu, ghi lại vào docs/th2/bao_cao/06_dashboard.md mục "Góp ý tài liệu cài đặt" để báo Tùng.
- Hướng dẫn tôi cấu hình Superset MCP theo CAI_DAT_MCP.md. Kiểm tra MCP hoạt động bằng cách liệt kê dataset.
  Nếu MCP không hoạt động sau 2 lần thử: KHÔNG tự sửa cấu hình hệ thống, chuyển sang làm bằng giao diện (bước 2B) và ghi
  lại lỗi để báo Tùng.
- Tạo nhánh: git checkout th2/main && git pull (nếu có remote) && git checkout -b th2/dashboard

BƯỚC 1 – XEM DỮ LIỆU: qua MCP (hoặc SQL Lab), cho tôi xem 5 dòng mẫu và số dòng của từng view ai.model_run,
ai.revenue_forecast, ai.churn_score, ai.interaction_sentiment. Giải thích mỗi view dùng để làm gì bằng 1–2 câu.

BƯỚC 2A – DỰNG BIỂU ĐỒ QUA MCP. Mọi biểu đồ lọc is_selected = true trừ khi ghi khác. Tên ĐÚNG như dưới:
Tab Tổng quan (dùng lại đúng câu lệnh Tùng đã ghi trong docs/th2/bao_cao/05_mcp.md nếu có):
  [Tổng quan] Độ chính xác các mô hình · [Tổng quan] Doanh thu thực tế và dự báo ·
  [Tổng quan] Số khách theo mức rủi ro rời bỏ · [Tổng quan] Tỉ lệ cảm xúc
Tab Dự báo:
  [Dự báo] Doanh thu dự báo tháng tới – Big Number, kind=future, tháng nhỏ nhất
  [Dự báo] Doanh thu thực tế và dự báo 6 tháng – đường: month; actual, forecast, lower, upper
  [Dự báo] So sánh 3 phương pháp trên 6 tháng kiểm tra – đường: kind=backtest, forecast tách theo method, thêm actual
           (KHÔNG lọc is_selected)
  [Dự báo] Sai số các phương pháp – bảng từ ai.model_run module=forecast: method, mae, rmse, mape, is_selected
Tab Rời bỏ:
  [Rời bỏ] Số khách theo mức rủi ro – cột theo risk_label (thứ tự Cao, Trung bình, Thấp)
  [Rời bỏ] 20 khách rủi ro cao nhất – bảng: customer_name, customer_type, customer_source, staff_name, last_order_date,
           total_spent, probability (định dạng %), sắp xếp probability giảm dần
  [Rời bỏ] Rủi ro trung bình theo nhóm khách – cột: customer_type, AVG(probability)
  [Rời bỏ] So sánh mô hình – bảng từ ai.model_run module=churn: method, auc, precision, recall, f1, is_selected
Tab Cảm xúc:
  [Cảm xúc] Cảm xúc theo tháng – cột chồng: tháng của interaction_date × label_pred
  [Cảm xúc] Cảm xúc theo kênh – cột chồng: channel × label_pred
  [Cảm xúc] Độ chính xác: từ điển và Gemini – bảng từ ai.model_run module=sentiment: method, accuracy, macro_f1
  [Cảm xúc] Dự đoán đúng và sai – bảng chéo label_true × label_pred, đếm số câu (KHÔNG lọc is_selected nếu muốn so
            cả 2 phương pháp; khi đó tách theo method)
Với MỖI biểu đồ:
  (1) ghi NGUYÊN VĂN câu lệnh tiếng Việt đã dùng và tool MCP đã gọi;
  (2) kiểm tra số liệu: chạy một câu SQL đọc trực tiếp view tương ứng và so với số trên biểu đồ (ít nhất 2 con số);
  (3) nếu sai thì sửa biểu đồ, ghi lại đã sai gì.
Nhãn hiển thị tiếng Việt, tiền định dạng VNĐ, tỉ lệ định dạng %.

BƯỚC 2B – CHỈ KHI MCP KHÔNG DÙNG ĐƯỢC: hướng dẫn tôi tạo từng biểu đồ trên giao diện Superset (Charts → + Chart →
chọn dataset → loại biểu đồ → kéo cột nào vào đâu → Save). Mỗi lần một biểu đồ, chờ tôi báo xong rồi mới sang cái tiếp.

BƯỚC 3 – GHÉP DASHBOARD: dashboard "SmartCRM – AI Insights" (slug smartcrm-ai-insights) ĐÃ CÓ SẴN khung do
superset/bootstrap_th2.py tạo (tab Tổng quan). KHÔNG tạo dashboard mới: thêm 3 tab Dự báo · Rời bỏ · Cảm xúc vào đúng
dashboard này, giữ thứ tự Tổng quan · Dự báo · Rời bỏ · Cảm xúc. Nếu 4 biểu đồ Tổng quan chưa có trên máy tôi thì tạo
chúng trước rồi chạy lại python superset/bootstrap_th2.py để có khung. Nếu MCP không sắp được bố cục/tab thì hướng dẫn tôi kéo thả trên giao diện
(Edit dashboard → Tabs → kéo biểu đồ vào). Thêm bộ lọc: Nhóm khách (customer_type), Mức rủi ro (risk_label), Kênh
(channel), áp dụng đúng biểu đồ có cột đó. Thêm 1 khối Markdown đầu tab Tổng quan giải thích nguồn dữ liệu và rằng
số liệu lấy từ batch mô hình mới nhất.

BƯỚC 4 – GHI TÀI LIỆU (chỉ tạo/sửa các file này):
- docs/th2/bao_cao/06_dashboard.md: mục đích từng tab, bảng danh sách biểu đồ (tên, dataset, loại, cột, bộ lọc, câu hỏi
  kinh doanh nó trả lời, tạo bằng MCP hay giao diện), kết quả kiểm tra số liệu từng biểu đồ, danh sách ảnh cần chụp.
- Điền mục "4.5. Phần của Hoàng Anh" trong docs/th2/bao_cao/05_mcp.md: nguyên văn các câu lệnh MCP và kết quả. Không sửa
  phần của Tùng.
- Commit bằng tài khoản git của tôi. KHÔNG push.

RÀNG BUỘC:
- KHÔNG sửa bất kỳ file code nào (*.py, *.html, *.sql, docker-compose.yml, superset/), không sửa .env, không tạo/sửa
  tài khoản hay quyền trong Superset, không xoá biểu đồ/dashboard của người khác.
- Tài khoản MCP chỉ đọc dữ liệu; nếu một thao tác bị từ chối quyền thì báo tôi, không tìm cách vượt quyền.

KẾT THÚC: báo danh sách biểu đồ đã tạo (id, tên, bằng MCP hay giao diện), kết quả kiểm tra số liệu, link dashboard,
những việc tôi cần tự làm (chụp ảnh, push, báo Tùng).
```

---

## GIAI ĐOẠN 2 – Nối dữ liệu thật, kiểm tra lại và xuất dashboard (tuần 3)

```text
Tiếp tục phần dashboard TH2 của tôi (Hoàng Anh). Tùng báo đã có kết quả mô hình thật. Đọc lại docs/th2/HOP_DONG_DU_LIEU.md
và docs/th2/bao_cao/06_dashboard.md (tài liệu tôi đã viết ở giai đoạn 1).

VIỆC CẦN LÀM:
1. Hướng dẫn tôi cập nhật nhánh (git checkout th2/dashboard && git merge th2/main), chạy migrate nếu có, rồi chạy
   `python manage.py run_ai_pipeline` để có batch thật trên máy tôi (nếu thiếu dữ liệu nạp thì làm theo docs/th2/CAI_DAT.md).
   Nhờ chạy lại sql/superset/03_ai_views.sql theo CAI_DAT.md.
2. Kiểm tra qua MCP/SQL: các view ai.* không còn batch "demo", có đúng 1 phương pháp is_selected mỗi module.
3. Mở lại TỪNG biểu đồ: làm mới dữ liệu, kiểm tra lại số liệu bằng SQL như giai đoạn 1 (ít nhất 2 con số mỗi biểu đồ),
   sửa nếu sai (ví dụ trục, định dạng, thứ tự). Cập nhật bảng kiểm tra trong 06_dashboard.md (thêm cột "dữ liệu thật").
4. Hướng dẫn tôi XUẤT dashboard (Dashboards → chọn → Export) ra file ZIP, lưu vào
   docs/th2/dashboard/smartcrm_ai_insights_export.zip để Tùng nhập lên máy chính.
5. Liệt kê danh sách ảnh cần chụp (mỗi tab 1 ảnh, cộng ảnh từng biểu đồ quan trọng), tên file gợi ý
   docs/th2/dashboard/img/<tab>_<ten>.png, và chỗ chèn ảnh trong 06_dashboard.md.
6. Viết 3–5 nhận định kinh doanh rút ra từ dashboard (ví dụ tháng nào dự báo cao, nhóm khách nào rủi ro cao, kênh nào
   nhiều phản hồi tiêu cực) – mỗi nhận định ghi rõ đọc từ biểu đồ nào, con số nào. Thêm vào 06_dashboard.md.
7. Commit. KHÔNG push.

RÀNG BUỘC: như giai đoạn 1 – không sửa code, .env, tài khoản, quyền.
KẾT THÚC: báo kết quả kiểm tra lại, đường dẫn file ZIP, danh sách ảnh cần chụp, các nhận định.
```

---

## (Tuỳ chọn – chỉ khi dư thời gian, hỏi Tùng trước) Trang danh sách đơn hàng chỉ xem

```text
Tôi là Hoàng Anh, nhóm TH2 SmartCRM. Tùng đã đồng ý cho tôi làm thêm trang danh sách đơn hàng CHỈ XEM. Tạo nhánh
th2/trang-don-hang từ th2/main. Đọc crm/views.py (customer_list), crm/urls.py, crm/templates/crm/customer_list.html,
crm/templates/crm/base.html, crm/tests/test_views.py để làm giống phong cách sẵn có.
Làm: trang /crm/orders/ (staff mới xem được, giống customer_list): tìm theo mã đơn hoặc tên khách, lọc trạng thái, 20
đơn/trang, cột mã đơn, khách (link trang khách), trạng thái (badge), tổng tiền, ngày đặt; bấm mã đơn mở trang sửa trong
Admin. KHÔNG có nút thêm/sửa/xoá trên trang này, KHÔNG sửa models/migrations. Thêm mục "Đơn hàng" vào menu base.html.
Viết test trong crm/tests/test_orders_page.py (chưa đăng nhập bị chặn, lọc đúng, tìm đúng). Toàn bộ `python manage.py test`
phải qua. Commit, không push. Báo file đã tạo/sửa và kết quả test.
```
