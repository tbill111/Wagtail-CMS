# Prompt TH2 – Hoàng Hưng: Kiểm thử, đối chiếu số liệu, báo cáo và video

> **Cách dùng:** 2 giai đoạn. Giai đoạn 1 làm ngay khi Tùng gộp giai đoạn A. Giai đoạn 2 làm ở tuần 4, khi tất cả nhánh
> đã gộp vào `th2/main`. Mở Claude Code tại thư mục `smartcrm/`, dán từng khối.

---

## GIAI ĐOẠN 1 – Cài đặt thử, lệnh kiểm tra tự động, khung báo cáo (tuần 1–2)

```text
Bạn là kỹ sư kiểm thử Python/Django làm việc trong repo SmartCRM (Wagtail 8/Django 6, Python 3.13, PostgreSQL).
Tôi là Hoàng Hưng, thành viên nhóm TH2 "Hệ thống phân tích dữ liệu thông minh tích hợp AI và Apache Superset".
Phần của tôi: kiểm thử và đối chiếu số liệu, gộp báo cáo kỹ thuật, kịch bản video (checklist 05). Tôi mới học, hãy giải
thích từng bước ngắn gọn bằng tiếng Việt.

BƯỚC 0 – ĐỌC VÀ KIỂM TRA (bắt buộc):
- Đọc HẾT docs/th2/HOP_DONG_DU_LIEU.md, docs/th2/CAI_DAT.md, insights/models.py, insights/conf.py,
  crm/management/commands/verify_superset_data.py (lệnh đối chiếu của TH1 – làm theo phong cách này).
- Tạo nhánh: git checkout th2/main && git pull (nếu có remote) && git checkout -b th2/kiem-thu-bao-cao

BƯỚC 1 – CÀI ĐẶT THỬ TỪ ĐẦU: hướng dẫn tôi làm theo docs/th2/CAI_DAT.md trên máy tôi, từng bước. Ghi lại MỌI chỗ tài liệu
sai, thiếu, khó hiểu, lệnh lỗi và cách đã xử lý vào docs/th2/bao_cao/08_kiem_thu_doi_chieu.md mục "Kiểm thử hướng dẫn cài
đặt" (bảng: bước, vấn đề, cách xử lý, đề xuất sửa tài liệu). Không tự sửa CAI_DAT.md – để Tùng sửa.

BƯỚC 2 – LỆNH KIỂM TRA TỰ ĐỘNG `python manage.py verify_ai_results` (file mới
insights/management/commands/verify_ai_results.py). CHỈ ĐỌC, không ghi gì vào CSDL. Kiểm tra batch thành công mới nhất
của từng module (bỏ qua batch "demo", in cảnh báo nếu chỉ có demo):
  A. Chung: mỗi module có đúng 1 ModelRun is_selected trong batch; mọi ModelRun success có đủ khoá metrics theo mục 5
     hợp đồng; is_selected đúng tiêu chí (mape nhỏ nhất / auc lớn nhất / macro_f1 lớn nhất).
  B. Dự báo: actual của các dòng history + backtest khớp doanh thu tháng tính lại từ ORM (Σ quantity × unit_price đơn
     Hoàn thành, giờ VN), sai lệch ≤ 1 đồng; mỗi phương pháp có đúng 6 dòng future và 6 dòng backtest;
     lower ≤ forecast ≤ upper; tính lại MAE, RMSE, MAPE từ các dòng backtest và so với metrics (sai lệch ≤ 0,01).
  C. Rời bỏ: mọi khách có ≥ 1 đơn Hoàn thành đến reference_date đều có điểm ở mỗi phương pháp; probability trong [0, 1];
     risk_band đúng ngưỡng RISK_HIGH/RISK_MEDIUM; in số khách theo từng mức.
  D. Cảm xúc: mọi SentimentResult có label hợp lệ; tính lại accuracy và macro_f1 từ SentimentResult so với
     SentimentLabel và so với metrics (sai lệch ≤ 0,001).
  E. Nếu đang chạy trên PostgreSQL và schema ai tồn tại: số dòng của 4 view ai.* khớp với số tính từ ORM cho batch mới
     nhất (dùng connection.cursor(), chỉ SELECT).
  In bảng kết quả từng mục: Kiểm tra · Kết quả · KHỚP/LỆCH (giống verify_superset_data), cuối cùng tổng kết số mục
  khớp/lệch, thoát mã 1 nếu có mục lệch. Có tuỳ chọn --module forecast|churn|sentiment.

BƯỚC 3 – TEST cho lệnh trên (file mới insights/tests/test_verify_ai_results.py), dữ liệu giả tự tạo trong test: trường
hợp đúng hết → KHỚP; cố tình làm sai 1 metrics → báo LỆCH và mã thoát 1; chỉ có batch demo → cảnh báo.
Chạy `python manage.py test` – TOÀN BỘ test phải qua.

BƯỚC 4 – KHUNG BÁO CÁO: tạo docs/TH2_BAO_CAO.md với mục lục và các phần (để trống chỗ, ghi "chờ <tên người>"):
  1. Tổng quan đề tài, mục tiêu, thành viên và phân công
  2. Kiến trúc và luồng dữ liệu (checklist 01) ← 01_kien_truc.md
  3. Mô hình AI (checklist 02, 06): 3.1 Dự báo ← 02_du_bao.md · 3.2 Rời bỏ ← 03_roi_bo.md · 3.3 Cảm xúc ← 04_cam_xuc.md
  4. Superset MCP (checklist 03) ← 05_mcp.md
  5. Dashboard AI Insights (checklist 04) ← 06_dashboard.md
  6. Kiểm thử và đối chiếu số liệu (checklist 05) ← 08_kiem_thu_doi_chieu.md
  7. Đề xuất mô hình và phương pháp mở rộng (checklist 06) ← 07_de_xuat_mo_rong.md
  8. Hướng dẫn cài đặt ← docs/th2/CAI_DAT.md (tóm tắt + link)
  9. Kết luận, hạn chế, hướng phát triển
  Phụ lục A: bảng "Checklist ↔ bằng chứng" (6 mục, mỗi mục: yêu cầu, việc đã làm, file/ảnh chứng minh, người làm).
Commit bằng tài khoản git của tôi. KHÔNG push.

RÀNG BUỘC:
- Chỉ tạo/sửa: insights/management/commands/verify_ai_results.py, insights/tests/test_verify_ai_results.py,
  docs/th2/bao_cao/08_kiem_thu_doi_chieu.md, docs/TH2_BAO_CAO.md, docs/th2/KICH_BAN_VIDEO_TH2.md.
- KHÔNG sửa models, migrations, insights/pipeline/*, crm/*, sql/*, superset/*, .env, file báo cáo của người khác.
- Lệnh kiểm tra tuyệt đối không ghi/xoá dữ liệu.

KẾT THÚC: báo kết quả cài đặt thử (các vấn đề gặp), file đã tạo, kết quả test, kết quả chạy verify_ai_results trên dữ
liệu hiện có.
```

---

## GIAI ĐOẠN 2 – Đối chiếu thật, gộp báo cáo, kịch bản video (tuần 4)

```text
Tiếp tục phần của tôi (Hoàng Hưng) trong TH2 SmartCRM. Mọi nhánh đã gộp vào th2/main. Đọc lại
docs/th2/HOP_DONG_DU_LIEU.md và các file trong docs/th2/bao_cao/.

VIỆC CẦN LÀM:
1. Cập nhật nhánh: git checkout th2/kiem-thu-bao-cao && git merge th2/main. Chạy migrate, `python manage.py
   run_ai_pipeline`, rồi `python manage.py verify_ai_results`. Mục nào LỆCH: ghi rõ vào 08_kiem_thu_doi_chieu.md và soạn
   tin nhắn ngắn gửi đúng người phụ trách (Ngọc Anh: dự báo, Thái Anh: rời bỏ, Tùng: cảm xúc/view) – không tự sửa code.
2. Đối chiếu dashboard: với từng biểu đồ trong docs/th2/bao_cao/06_dashboard.md, hướng dẫn tôi mở dashboard, đọc 2 con số
   trên biểu đồ, rồi chạy câu SQL tương ứng trên view ai.* (tôi chạy trong Superset SQL Lab) để so. Lập bảng: biểu đồ, con
   số trên dashboard, con số từ SQL, KHỚP/LỆCH. Ghi vào 08_kiem_thu_doi_chieu.md.
3. Kiểm tra trang SmartCRM: /crm/analytics/ hiện tab AI Insights; trang chi tiết một khách rủi ro cao hiện "Rủi ro rời bỏ"
   khớp với ai.churn_score. Ghi kết quả.
4. Gộp báo cáo docs/TH2_BAO_CAO.md: chép nội dung các file 01–08 vào đúng mục (giữ nguyên số liệu, chỉ sửa chính tả và
   nối câu cho liền mạch), thống nhất thuật ngữ và định dạng số (VNĐ, %, dấu thập phân phẩy). Hoàn thiện Phụ lục A
   "Checklist ↔ bằng chứng". Chỗ nào còn "chờ <tên>" thì liệt kê ra để tôi nhắc người đó.
5. Viết docs/th2/KICH_BAN_VIDEO_TH2.md: tổng 12–15 phút, mỗi thành viên tự trình bày phần mình. Bảng theo thời gian:
   phút, người nói, checklist, màn hình/thao tác, lời thoại gợi ý (ngắn, dễ đọc). Thứ tự: Tùng (giới thiệu, kiến trúc 01,
   dữ liệu) → Ngọc Anh (dự báo) → Thái Anh (rời bỏ + trang khách) → Tùng (cảm xúc, demo MCP trực tiếp 03) → Hoàng Anh
   (dashboard 04) → Hoàng Hưng (kiểm thử, verify_ai_results, đối chiếu 05) → Tùng (đề xuất mở rộng 06, kết luận).
   Kèm danh sách chuẩn bị trước khi quay (dịch vụ cần chạy, tab cần mở, dữ liệu cần có) và lưu ý không lộ .env/mật khẩu.
6. Commit. KHÔNG push.

KẾT THÚC: báo kết quả verify_ai_results, bảng đối chiếu dashboard (số mục khớp/lệch), các mục báo cáo còn thiếu và cần
nhắc ai, đường dẫn kịch bản video.
```
