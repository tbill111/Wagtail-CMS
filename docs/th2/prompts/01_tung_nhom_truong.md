# Prompt TH2 – Tùng (nhóm trưởng)

> **Cách dùng:** mở Claude Code tại thư mục `smartcrm/`. Prompt chia **4 giai đoạn**: dán **từng giai đoạn một**, chờ
> agent báo xong và tự kiểm tra kết quả rồi mới dán giai đoạn tiếp theo. Giai đoạn A phải gộp vào `th2/main` sớm nhất
> (cả nhóm đang chờ).

---

## GIAI ĐOẠN A – Nền tảng: CSDL TH2, nạp dữ liệu thật, app `insights` (tuần 1)

```text
Bạn là kỹ sư Django/PostgreSQL làm việc trong repo SmartCRM (Wagtail 8, Django 6, Python 3.13, PostgreSQL 16 và
Apache Superset 4.1.2 chạy bằng docker compose). Tôi là Tùng, nhóm trưởng bài TH2 "Hệ thống phân tích dữ liệu thông minh
tích hợp AI và Apache Superset". Đây là giai đoạn A: dựng nền tảng để 4 thành viên khác bắt đầu được.

ĐỌC TRƯỚC KHI LÀM (bắt buộc, đọc hết):
- docs/th2/HOP_DONG_DU_LIEU.md  ← luật chung của cả nhóm. Mọi tên bảng, tên trường, tên phương pháp, khoá metrics, hằng
  số phải đúng y như file này. Nếu thấy điểm nào không làm được, DỪNG LẠI hỏi tôi, không tự đổi.
- docs/TH1_SUPERSET.md, sql/superset/*.sql, crm/models.py, crm/analytics.py, crm/services/ai_service.py,
  crm/management/commands/seed_superset.py, smartcrm/settings/base.py, docker-compose.yml.

VIỆC CẦN LÀM:
1. Git: từ nhánh th1/superset tạo nhánh th2/main (git checkout -b th2/main), rồi tạo nhánh th2/nen-tang từ th2/main.
2. CSDL riêng cho TH2: tạo database smartcrm_th2 trong container db (owner là DB_USER hiện tại). Hướng dẫn tôi sửa .env:
   DB_NAME=smartcrm_th2 (KHÔNG tự sửa .env, chỉ in ra dòng cần sửa). Sau khi tôi sửa: chạy migrate, tạo tài khoản admin
   bằng `createsuperuser` (để tôi tự nhập mật khẩu – in lệnh ra cho tôi chạy).
3. App mới `insights`:
   - models đúng mục 4 của hợp đồng (ModelRun, RevenueForecast, ChurnScore, SentimentLabel, SentimentResult), có
     verbose_name tiếng Việt, migration 0001_initial.
   - insights/conf.py: các hằng số (kể cả SENTIMENT_SAMPLE) và hàm reference_date() đúng mục 6.
   - insights/pipeline/__init__.py với MODULES rỗng có sẵn chỗ cho forecast, churn, sentiment (import lười để module chưa
     có thì bỏ qua và báo "chưa có module").
   - Lệnh `python manage.py run_ai_pipeline [--only ...]` đúng mục 6: sinh batch, xoá batch "demo", gọi từng module,
     in bảng tóm tắt (module, method, status, metric chính, is_selected).
   - Lệnh `python manage.py seed_ai_demo`: ghi kết quả GIẢ nhưng đúng cấu trúc vào batch "demo" cho cả 3 module
     (24 tháng history + 6 backtest + 6 future; churn cho mọi khách; sentiment cho mọi InteractionLog có nhãn) để
     Hoàng Anh dựng dashboard trước khi mô hình thật xong. Chạy được nhiều lần (xoá batch demo cũ trước).
   - Đăng ký insights vào INSTALLED_APPS; thêm vào Wagtail Admin một nhóm menu "Kết quả AI" chỉ xem (dùng lại
     ReadOnlyPermissionPolicy kiểu AIReport trong crm/wagtail_hooks.py) cho ModelRun.
4. Thêm vào requirements.txt, ghim phiên bản cụ thể tương thích Python 3.13: pandas, numpy, scikit-learn, statsmodels.
   Cài vào venv và kiểm tra import được.
5. Lệnh nạp dữ liệu thật `python manage.py import_th2_data --retail <đường dẫn file> --reviews <đường dẫn file>`
   (đặt ở insights/management/commands/), đúng mục 3 của hợp đồng:
   a) Online Retail II: hướng dẫn tôi tải file từ trang UCI (in link, tôi tự tải) vào thư mục data/ (thêm data/ vào
      .gitignore). Đọc cả 2 sheet, bỏ dòng không có Customer ID, lấy mẫu 2.000 khách random_state=42, dời +14 năm,
      GBP→VNĐ tỉ giá 33.000, hoá đơn "C…" là đơn Huỷ, còn lại Hoàn thành, gộp dòng trùng sản phẩm trong cùng hoá đơn.
      Sản phẩm track_stock=False. Mã đơn giữ đúng định dạng của Order.generate_code theo ngày đặt.
      Được dùng bulk_create cho hiệu năng NHƯNG kết quả phải giống như tạo qua model (mã đơn, created_at, stock_snapshot
      rỗng). Có tuỳ chọn --clear để xoá dữ liệu cũ trước khi nạp. In thống kê cuối: số khách, đơn, dòng, sản phẩm,
      khoảng thời gian, tổng doanh thu đơn Hoàn thành.
   b) Văn bản tiếng Việt có nhãn cảm xúc: tìm một bộ dữ liệu công khai phù hợp (ứng viên: UIT-VSFC, UIT-ViSFD hoặc bộ
      nhận xét sản phẩm tiếng Việt trên Hugging Face). Kiểm tra giấy phép thật sự cho phép dùng học tập, báo tôi chọn
      trước khi viết code. Nạp khoảng 3.000 câu thành InteractionLog (kênh chọn ngẫu nhiên random_state=42, ngày nằm trong
      khoảng khách đó đang mua hàng), nhãn đúng vào SentimentLabel (positive/neutral/negative). Không có bộ nào dùng được
      thì DỪNG LẠI báo tôi.
   c) Chạy nạp thật, chạy lại sql/superset/01_analytics_views.sql và 02_superset_readonly_user.sql trên smartcrm_th2.
6. sql/superset/03_ai_views.sql: tạo schema ai và 4 view đúng mục 7 (chỉ lấy batch thành công mới nhất mỗi module, bỏ
   batch demo khi đã có batch thật), GRANT USAGE/SELECT cho superset_ro, có bảng VERIFY cuối file như 01/02.
   Chạy file trên smartcrm_th2 sau khi seed_ai_demo.
7. Superset: thêm kết nối "SmartCRM TH2 (chỉ đọc)" tới smartcrm_th2 bằng superset_ro (làm theo cách ensure_database trong
   superset/bootstrap_dashboard.py, viết script mới superset/bootstrap_th2.py, không sửa script TH1). Đăng ký 4 dataset
   ai.* với nhãn cột tiếng Việt.
8. Test: insights/tests/test_pipeline.py (run_ai_pipeline với module giả, seed_ai_demo, reference_date). Chạy toàn bộ
   `python manage.py test` phải qua hết (cả test cũ).
9. Viết docs/th2/CAI_DAT.md: cài từ đầu trên máy mới (clone, venv, .env, docker, tạo DB, migrate, tải dữ liệu, nạp,
   SQL 01–03, seed_ai_demo, bootstrap_th2). Viết phần "Dữ liệu" và "Kiến trúc" trong docs/th2/bao_cao/01_kien_truc.md.
10. Commit theo từng bước trên th2/nen-tang. KHÔNG push, KHÔNG gộp – báo tôi để tôi xem rồi tự gộp.

RÀNG BUỘC:
- Không sửa dữ liệu hay cấu trúc của CSDL smartcrm (TH1). Không sửa script/SQL của TH1, chỉ thêm file mới.
- Không ghi mật khẩu vào file nào được commit. Không đọc/in nội dung .env.
- Không bịa thông tin bộ dữ liệu (số dòng, giấy phép): đọc từ trang gốc hoặc file thật.

KẾT THÚC: báo cáo ngắn gồm danh sách file đã tạo/sửa, kết quả test, thống kê dữ liệu đã nạp, bảng VERIFY của 03, và
những việc tôi phải tự làm (sửa .env, tải file, gộp nhánh).
```

---

## GIAI ĐOẠN B – Superset MCP (tuần 1–2)

```text
Tiếp tục bài TH2 SmartCRM, giai đoạn B: cấu hình Apache Superset MCP. Đọc lại docs/th2/HOP_DONG_DU_LIEU.md mục 2 và 8.
Làm trên nhánh th2/nen-tang (hoặc nhánh mới th2/mcp tách từ th2/main nếu A đã gộp).

BỐI CẢNH: Superset của dự án là 4.1.2 (docker compose, cổng theo SUPERSET_PORT trong .env). MCP chính thức của Apache
(superset/mcp_service) chỉ có từ Superset 6.x. MCP cộng đồng aptro/superset-mcp được tác giả thử với 4.1.1 và đăng nhập
bằng username/password. Hãy tự kiểm tra lại thông tin này trên trang gốc trước khi làm.

VIỆC CẦN LÀM:
1. Tìm hiểu aptro/superset-mcp (README, cách cài, biến môi trường, danh sách tool). Nếu không chạy được với 4.1.2 thì
   đề xuất phương án B: dựng một Superset 6.x riêng (compose profile riêng, cổng khác, KHÔNG đụng Superset TH1) dùng MCP
   chính thức. Báo tôi chọn trước khi làm phương án B.
2. Tạo trong Superset một tài khoản riêng cho MCP, ví dụ mcp_agent: KHÔNG phải Admin; chỉ đủ quyền đọc dataset trên kết
   nối "SmartCRM TH2 (chỉ đọc)" và tạo/sửa chart, dashboard. Ghi rõ danh sách quyền đã cấp. Mật khẩu để tôi tự đặt.
3. Cấu hình MCP cho Claude Code của dự án (file .mcp.json ở gốc smartcrm, mật khẩu đọc từ biến môi trường, KHÔNG ghi
   vào file). Hướng dẫn cấu hình tương đương cho Claude Desktop.
4. Kiểm thử gọi tool: liệt kê database, dataset; chạy 1 truy vấn đọc ai.model_run; thử một lệnh ghi bị chặn (ví dụ
   DELETE) để chứng minh tài khoản không ghi được dữ liệu.
5. Dùng MCP tạo 4 biểu đồ cho tab Tổng quan bằng câu lệnh tiếng Việt (tên theo quy ước mục 8):
   - [Tổng quan] Độ chính xác các mô hình (bảng từ ai.model_run)
   - [Tổng quan] Doanh thu thực tế và dự báo (đường, ai.revenue_forecast, phương pháp is_selected)
   - [Tổng quan] Số khách theo mức rủi ro rời bỏ (cột, ai.churn_score is_selected)
   - [Tổng quan] Tỉ lệ cảm xúc (tròn, ai.interaction_sentiment is_selected)
   Mỗi biểu đồ: kiểm tra số trên biểu đồ khớp với truy vấn SQL trực tiếp.
6. Viết docs/th2/CAI_DAT_MCP.md (để Hoàng Anh làm theo trên máy mình) và docs/th2/bao_cao/05_mcp.md: kiến trúc MCP,
   quyền tài khoản, danh sách tool đã dùng, NGUYÊN VĂN từng câu lệnh tôi đã gõ và kết quả, chỗ trống để chèn ảnh.
7. Commit. Không push.

KẾT THÚC: báo phương án đã dùng, quyền của tài khoản MCP, 4 biểu đồ đã tạo (id, tên), kết quả kiểm tra chặn ghi.
```

---

## GIAI ĐOẠN C – Module phân tích cảm xúc (tuần 2–3)

```text
Tiếp tục TH2 SmartCRM, giai đoạn C: module phân tích cảm xúc. Đọc lại docs/th2/HOP_DONG_DU_LIEU.md mục 4, 5, 6, 9.
Tạo nhánh th2/cam-xuc từ th2/main.

VIỆC CẦN LÀM: insights/pipeline/sentiment.py với run(batch) đúng hợp đồng, 2 phương pháp:
1. keyword: từ điển từ tích cực/tiêu cực tiếng Việt (đặt ở insights/pipeline/lexicon_vi.py), xử lý phủ định ("không",
   "chẳng", "chưa" đứng trước), chuẩn hoá chữ thường, bỏ dấu câu; điểm = tích cực − tiêu cực → positive/neutral/negative.
2. gemini: dùng lại GeminiCRMService()._generate(prompt, json_schema=...) trong crm/services/ai_service.py (đã có AI dự
   phòng và chế độ mô phỏng). Gửi theo lô 20 câu/lần, yêu cầu JSON [{id, label, confidence}], đo thời gian mỗi lô chia
   đều latency_ms. Tự nghỉ và thử lại khi gặp lỗi 429. Ở chế độ mô phỏng (AI_MOCK) thì ghi notes "mô phỏng" và KHÔNG
   được chọn is_selected.
- TẬP ĐÁNH GIÁ CHUNG: lấy mẫu phân tầng theo nhãn từ các InteractionLog có SentimentLabel, kích thước đặt bằng biến môi
  trường hoặc hằng số SENTIMENT_SAMPLE trong insights/conf.py (mặc định 600, 0 = tất cả), random_state=42. CẢ HAI phương
  pháp chấm ĐÚNG tập mẫu này (để so sánh công bằng và để verify_ai_results của Hoàng Hưng tính lại khớp).
- Đánh giá: accuracy, macro_f1, f1_by_class, confusion_matrix, n_eval, avg_latency_ms (dùng sklearn.metrics), tính trên
  toàn bộ SentimentResult của run đó. Ghi SentimentResult cho mọi câu đã chấm. Chọn is_selected theo macro_f1.
- Đăng ký "sentiment" trong MODULES. Test insights/tests/test_sentiment.py: từ điển và phủ định, parse JSON lỗi, Gemini
  được giả lập bằng mock (không gọi mạng trong test).
- Chạy thật `python manage.py run_ai_pipeline --only sentiment`, chạy lại sql 03 nếu cần, kiểm tra ai.interaction_sentiment.
- Viết docs/th2/bao_cao/04_cam_xuc.md theo đúng "Khung bắt buộc" mục 9, số liệu lấy từ batch vừa chạy, có cả chi phí và
  thời gian của Gemini so với từ điển.
- Toàn bộ test phải qua. Commit, không push.
```

---

## GIAI ĐOẠN D – Tích hợp, nhúng dashboard, đề xuất mở rộng (tuần 3–4)

```text
Tiếp tục TH2 SmartCRM, giai đoạn D: tích hợp cuối. Đọc lại docs/th2/HOP_DONG_DU_LIEU.md. Các nhánh th2/du-bao,
th2/roi-bo, th2/cam-xuc, th2/dashboard đã/đang được gộp vào th2/main. Làm trên nhánh th2/tich-hop từ th2/main.

VIỆC CẦN LÀM:
1. Review code của th2/du-bao và th2/roi-bo theo hợp đồng: đúng tên bảng, tên method, khoá metrics, is_selected, test
   có qua không. Liệt kê lỗi cần sửa cho từng người (KHÔNG tự sửa code của họ, chỉ báo).
2. Chạy toàn chuỗi: `python manage.py run_ai_pipeline`, chạy lại sql/superset/03_ai_views.sql, kiểm tra 4 view ai.* có
   dữ liệu batch thật và không còn batch demo.
3. Nhúng dashboard AI Insights vào SmartCRM: trang /crm/analytics/ hiện 2 tab "Phân tích kinh doanh" (dashboard TH1 nếu
   có trên CSDL này) và "AI Insights" (slug smartcrm-ai-insights). Mở rộng crm/services/superset.py để nhận slug theo tab,
   giữ nguyên cơ chế guest token và bảo mật của TH1. Bật nhúng cho dashboard mới (theo cách ensure_embedding trong
   superset/bootstrap_dashboard.py). Cập nhật test crm/tests/test_superset_embed.py.
4. Viết docs/th2/bao_cao/07_de_xuat_mo_rong.md (mục 06 – cộng điểm):
   - Bảng 4 họ phương pháp nhóm đã dùng: thống kê chuỗi thời gian, học máy, luật nghiệp vụ, LLM (kể cả 2 tính năng LLM
     sẵn có của SmartCRM: phân loại khách, báo cáo nhận định).
   - Đề xuất chưa làm, mỗi mục: mục đích kinh doanh, dữ liệu cần, phương pháp, cách đánh giá, độ khó: phân khúc K-Means,
     phát hiện bất thường doanh thu (Isolation Forest), gợi ý bán chéo (luật kết hợp), LLM gợi ý hành động cho khách rủi
     ro cao, hỏi đáp dữ liệu bằng tiếng Việt qua MCP.
5. Hoàn thiện docs/th2/bao_cao/01_kien_truc.md: sơ đồ mermaid luồng dữ liệu đầy đủ, bảng phân quyền các tài khoản
   (smartcrm, superset_ro, mcp_agent), các biện pháp bảo mật.
6. Toàn bộ test qua, `python manage.py check` không lỗi. Commit, không push.

KẾT THÚC: báo lỗi review của từng người, kết quả chạy toàn chuỗi (bảng tóm tắt), trạng thái nhúng dashboard.
```
