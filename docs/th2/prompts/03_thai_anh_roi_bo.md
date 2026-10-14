# Prompt TH2 – Thái Anh: Module dự đoán khách hàng rời bỏ

> **Cách dùng:** chỉ bắt đầu khi Tùng báo đã gộp giai đoạn A vào `th2/main`. Mở Claude Code tại thư mục `smartcrm/`,
> dán toàn bộ khối dưới đây.

```text
Bạn là kỹ sư học máy Python làm việc trong repo SmartCRM (Wagtail 8/Django 6, Python 3.13, PostgreSQL).
Tôi là Thái Anh, thành viên nhóm TH2 "Hệ thống phân tích dữ liệu thông minh tích hợp AI và Apache Superset".
Phần của tôi: MODULE DỰ ĐOÁN KHÁCH HÀNG RỜI BỎ (checklist 02, 05, 06) và hiển thị rủi ro trên trang khách của SmartCRM.

BƯỚC 0 – ĐỌC VÀ KIỂM TRA (bắt buộc):
- Đọc HẾT docs/th2/HOP_DONG_DU_LIEU.md. Tên bảng, trường, phương pháp, khoá metrics, hằng số (CHURN_WINDOW_DAYS,
  RISK_HIGH, RISK_MEDIUM, RANDOM_STATE) phải đúng y như file. Thấy mâu thuẫn thì DỪNG LẠI nói rõ cần hỏi Tùng điều gì.
- Đọc insights/models.py, insights/conf.py, insights/pipeline/__init__.py, crm/models.py (Customer, Order, OrderItem,
  InteractionLog), crm/views.py (customer_detail), crm/templates/crm/customer_detail.html, crm/tests/test_views.py.
- Kiểm tra: có nhánh th2/main; `python manage.py showmigrations insights` có 0001_initial [X];
  `python -c "import sklearn, pandas"` chạy được. Thiếu thì DỪNG LẠI báo tôi.
- Tạo nhánh: git checkout th2/main && git pull (nếu có remote) && git checkout -b th2/roi-bo

BƯỚC 1 – ĐỊNH NGHĨA NHÃN VÀ ĐẶC TRƯNG (insights/pipeline/churn.py):
- R = insights.conf.reference_date(); cutoff = R − CHURN_WINDOW_DAYS (180 ngày).
- Tập huấn luyện/đánh giá: khách có ≥ 1 đơn Hoàn thành TRƯỚC cutoff.
  Nhãn churned = 1 nếu KHÔNG có đơn Hoàn thành nào trong (cutoff, R]; ngược lại 0.
- Đặc trưng chỉ dùng dữ liệu ĐẾN cutoff (không được nhìn tương lai): recency_days, frequency (số đơn Hoàn thành),
  monetary (tổng chi), avg_order_value, tenure_days (từ đơn đầu), orders_last_90d, cancelled_orders, distinct_products,
  interactions_count. Viết hàm build_features(as_of_date) dùng chung cho huấn luyện (as_of=cutoff) và chấm điểm hiện tại
  (as_of=R). Tính bằng ORM/pandas, tránh truy vấn từng khách một.
- In ra tỉ lệ churn của tập. Nếu < 5% hoặc > 95% thì DỪNG LẠI báo tôi (nhãn lệch quá, cần bàn với Tùng).

BƯỚC 2 – 3 PHƯƠNG PHÁP (run(batch) -> list[ModelRun]). Mỗi phương pháp chạy qua
insights.pipeline.base.run_method(batch, "churn", method, func) (tự tạo ModelRun, bắt lỗi, làm tròn metrics; func trả
về MethodResult), cuối cùng select_best(runs, "auc", higher_is_better=True):
- Chia train/test 70/30, phân tầng theo nhãn, random_state=42.
- rfm_rule: không học máy – điểm = thứ hạng phần trăm của recency_days (càng lâu không mua càng cao), có thể kết hợp tần
  suất thấp; mô tả công thức trong params. Dùng điểm này làm "xác suất" để tính AUC.
- logistic_regression: StandardScaler + LogisticRegression(class_weight="balanced", max_iter=1000).
- random_forest: RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42).
  Ghi top 5 đặc trưng quan trọng vào params.

BƯỚC 3 – ĐÁNH GIÁ trên tập test (sklearn.metrics): auc, precision, recall, f1, accuracy (ngưỡng 0,5),
confusion_matrix [[tn, fp], [fn, tp]], churn_rate, n_train, n_test – đúng khoá mục 5, làm tròn 4 chữ số.
is_selected = AUC lớn nhất. Phương pháp lỗi → status="failed", các phương pháp khác vẫn chạy.

BƯỚC 4 – GHI KẾT QUẢ (bảng ChurnScore):
Với MỖI phương pháp: huấn luyện lại trên toàn bộ tập có nhãn, rồi chấm điểm MỌI khách có ≥ 1 đơn Hoàn thành tính đến R
bằng đặc trưng as_of=R. Ghi probability (0–1) và risk_band = insights.conf.risk_band(probability). Dùng bulk_create.
"churn" đã được đăng ký sẵn trong MODULES, chỉ cần tạo đúng file insights/pipeline/churn.py có hàm run(batch).

BƯỚC 5 – HIỂN THỊ TRÊN SMARTCRM (trang chi tiết khách /crm/customers/<id>/):
- Thêm một khối nhỏ "Rủi ro rời bỏ" trong cột thông tin khách: "78% – Cao" với màu theo mức (dùng class Bootstrap sẵn
  có: text-bg-danger/warning/success), dòng phụ "Mô hình <tên tiếng Việt của method> · cập nhật <ngày>".
  Lấy từ ChurnScore của phương pháp is_selected trong batch churn thành công mới nhất. Không có dữ liệu → "Chưa có dự
  đoán" màu xám. Tạo partial mới crm/templates/crm/_churn_risk.html, chỉ thêm 1 dòng include vào customer_detail.html
  và tối thiểu code trong view (hoặc một hàm trợ giúp trong insights). Không làm chậm trang: 1 truy vấn.
- Giữ nguyên giao diện và mọi chức năng cũ của trang.

BƯỚC 6 – TEST (insights/tests/test_churn.py), dữ liệu giả tự tạo trong test:
- Nhãn đúng định nghĩa (khách mua sau cutoff = 0, không mua = 1); đặc trưng không dùng dữ liệu sau cutoff.
- Cả 3 phương pháp chạy, đủ khoá metrics, đúng 1 is_selected, probability trong [0, 1], risk_band đúng ngưỡng.
- Trang chi tiết khách hiện khối rủi ro khi có dữ liệu và "Chưa có dự đoán" khi không có.
Chạy `python manage.py test` – TOÀN BỘ test (kể cả test cũ của crm) phải qua.

BƯỚC 7 – CHẠY THẬT: `python manage.py run_ai_pipeline --only churn`, in bảng so sánh 3 phương pháp và số khách theo
mức rủi ro. Mở thử một trang khách rủi ro cao để kiểm tra hiển thị.

BƯỚC 8 – BÁO CÁO: viết docs/th2/bao_cao/03_roi_bo.md theo ĐÚNG "Khung bắt buộc" mục 9 (8 phần), số liệu từ batch vừa chạy,
ghi mã batch. Giải thích bằng lời dễ hiểu: Precision = trong số khách bị báo sắp bỏ, bao nhiêu % bỏ thật; Recall = trong số
khách bỏ thật, bắt được bao nhiêu %; AUC từ 0,5 (đoán bừa) đến 1. Có ma trận nhầm lẫn dạng bảng, top đặc trưng quan
trọng, gợi ý hành động cho nhân viên. Hạn chế: định nghĩa rời bỏ 180 ngày là quy ước, dữ liệu shop nước ngoài.

RÀNG BUỘC:
- Chỉ tạo/sửa: insights/pipeline/churn.py, insights/tests/test_churn.py, crm/templates/crm/_churn_risk.html, 1 dòng
  include trong customer_detail.html, phần tối thiểu trong crm/views.py (customer_detail), docs/th2/bao_cao/03_roi_bo.md. Không sửa models, migrations, file của người khác, .env.
- Không thêm thư viện mới. Không gọi mạng.
- Commit nhỏ theo bước bằng tài khoản git của tôi. KHÔNG push.

KẾT THÚC: báo file đã tạo/sửa, kết quả test, bảng so sánh 3 phương pháp, số khách theo mức rủi ro, mã batch, và việc tôi
cần làm tiếp (push, mở PR vào th2/main, báo Hoàng Anh và Hoàng Hưng).
```
