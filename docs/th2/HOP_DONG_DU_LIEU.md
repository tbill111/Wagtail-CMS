# TH2 – Hợp đồng dữ liệu và quy ước chung

> **Mọi thành viên và mọi agent phải đọc file này trước khi làm.** Đây là "luật chung" để code của 5 người ghép vào
> nhau không vỡ. Muốn đổi bất cứ điều gì trong file này: báo Tùng (nhóm trưởng), Tùng sửa file rồi báo cả nhóm.

## 1. Thành viên, nhánh git và phần việc

| Người | Vai trò | Nhánh git | Checklist |
|---|---|---|---|
| **Tùng** (nhóm trưởng) | Kiến trúc, dữ liệu, Superset MCP, module cảm xúc, tích hợp | `th2/nen-tang` | 01, 03, 06 (+ 02, 05) |
| **Ngọc Anh** | Module dự báo doanh thu | `th2/du-bao` | 02, 05, 06 |
| **Thái Anh** | Module dự đoán khách rời bỏ | `th2/roi-bo` | 02, 05, 06 |
| **Hoàng Anh** | Dashboard AI Insights trên Superset | `th2/dashboard` | 03, 04 |
| **Hoàng Hưng** | Kiểm thử, đối chiếu số liệu, báo cáo, video | `th2/kiem-thu-bao-cao` | 05 |

- Nhánh gốc của TH2: **`th2/main`** (Tùng tạo từ `th1/superset`). Mọi người tách nhánh từ `th2/main`, làm xong mở
  Pull Request vào `th2/main`, Tùng review rồi gộp.
- **Thứ tự phụ thuộc:** Tùng gộp `th2/nen-tang` (giai đoạn A) vào `th2/main` **trước**. Người khác chỉ bắt đầu code sau khi
  `python manage.py showmigrations insights` hiện migration `0001_initial` đã áp dụng.
- Commit bằng **tài khoản git của chính mình**. Không commit file `.env`, dữ liệu tải về (`data/`), mật khẩu.

## 2. Kiến trúc tổng thể

```
SmartCRM (Wagtail/Django)
  ├─ crm, care          : bảng nghiệp vụ gốc (schema public)
  └─ insights (app mới) : bảng kết quả AI (schema public, tiền tố insights_)
           ▲  ghi bằng Django ORM                         │
  python manage.py run_ai_pipeline                         │
  (insights/pipeline/forecast.py · churn.py · sentiment.py)│
                                                           ▼
PostgreSQL ─ schema analytics (view TH1) ─ schema ai (view đọc kết quả AI, mới)
                                                           │ superset_ro chỉ SELECT
                                                           ▼
Apache Superset 4.1.2 ◀── Superset MCP (aptro/superset-mcp) ◀── Claude (agent)
   └─ dashboard "SmartCRM – AI Insights" (slug smartcrm-ai-insights)
         └─ nhúng vào SmartCRM: /crm/analytics/ (guest token, có từ TH1)
```

- **CSDL của TH2 là `smartcrm_th2`** (cùng container PostgreSQL, tách khỏi `smartcrm` của TH1 để TH1 vẫn nguyên vẹn).
  Trong `.env` mỗi người: `DB_ENGINE=postgres`, `DB_NAME=smartcrm_th2`.
- Superset dùng kết nối riêng **"SmartCRM TH2 (chỉ đọc)"** tới `smartcrm_th2` bằng tài khoản `superset_ro`.

## 3. Dữ liệu

- **Bán hàng:** bộ **Online Retail II** (UCI, giao dịch thật 12/2009 – 12/2011), nạp bằng
  `python manage.py import_th2_data`. Quy ước khi nạp:
  - Lấy mẫu **2.000 khách** có mã khách, `random_state=42` (mọi máy ra cùng một bộ).
  - **Dời mốc thời gian +14 năm** (giữ nguyên tháng → giữ mùa vụ): 12/2009 → 12/2023, 12/2011 → 12/2025.
  - **Đổi tiền: 1 GBP = 33.000 VNĐ** (tỉ giá cố định, ghi trong báo cáo), làm tròn đến đồng.
  - Hoá đơn mã bắt đầu bằng `C` → đơn **Huỷ**; còn lại → **Hoàn thành**.
  - Sản phẩm nhập về có `track_stock=False` (bộ dữ liệu không có tồn kho).
  - Khách không có tên/email thật → tên `Khách UK-<mã>`, email `uk<mã>@khach.smartcrm.local`, nguồn `website`.
- **Văn bản cảm xúc:** Hugging Face `anotherpolarbear/vietnamese-sentiment-analysis` (MIT, nhận xét điện thoại tiếng
  Việt 1–5 sao; 1–2 = tiêu cực, 3 = trung lập, 4–5 = tích cực), lấy mẫu phân tầng 3.000 câu, nạp thành
  `InteractionLog` gắn ngẫu nhiên (`random_state=42`) cho các khách đã mua, nhãn đúng lưu ở `insights.SentimentLabel`. **Việc gắn văn bản vào khách là nhân tạo – phải ghi rõ trong báo cáo.**
- **Ngày tham chiếu** (`reference_date`) = ngày của đơn hàng muộn nhất trong CSDL, **không dùng ngày hôm nay**.
  Lấy bằng `insights.conf.reference_date()`.
- **Doanh thu** = Σ `quantity × unit_price` của đơn **Hoàn thành**, gom theo tháng **giờ Việt Nam** – đúng quy ước TH1.
  Chỉ dùng **tháng trọn vẹn** (bỏ tháng cuối nếu chưa hết tháng).

## 4. App `insights` – bảng kết quả AI (Tùng tạo)

Mỗi lần chạy `run_ai_pipeline` sinh một **`batch`** (chuỗi `YYYYMMDD-HHMMSS`). Trong một batch, **mỗi phương pháp của mỗi
module = 1 dòng `ModelRun`**. Mỗi module đánh dấu đúng **1** phương pháp tốt nhất `is_selected=True` trong batch đó.

### `ModelRun`
| Trường | Kiểu | Ghi chú |
|---|---|---|
| `batch` | CharField(20), index | |
| `module` | CharField: `forecast` · `churn` · `sentiment` | |
| `method` | CharField(40) | xem bảng tên phương pháp ở mục 5 |
| `is_selected` | Boolean | phương pháp tốt nhất của module trong batch |
| `status` | CharField: `success` · `failed` | |
| `started_at`, `finished_at` | DateTime | |
| `n_rows` | Integer | số dòng kết quả đã ghi |
| `metrics` | JSON | **khoá theo mục 5** |
| `params` | JSON | tham số mô hình |
| `notes` | Text | cảnh báo, lỗi |

### `RevenueForecast` (Ngọc Anh ghi)
| Trường | Kiểu | Ghi chú |
|---|---|---|
| `run` | FK ModelRun, `related_name="forecasts"` | |
| `month` | Date (ngày 1 của tháng) | |
| `kind` | CharField: `history` · `backtest` · `future` | history: chỉ có `actual`; backtest: có cả hai; future: chỉ có dự báo |
| `actual` | Decimal(18,0), null | doanh thu thật (VNĐ) |
| `forecast`, `lower`, `upper` | Decimal(18,0), null | dự báo và khoảng tin cậy 95% |
| ràng buộc | unique (`run`, `month`, `kind`) | |

### `ChurnScore` (Thái Anh ghi)
| Trường | Kiểu | Ghi chú |
|---|---|---|
| `run` | FK ModelRun, `related_name="churn_scores"` | |
| `customer` | FK `crm.Customer`, CASCADE | |
| `probability` | Float 0–1 | xác suất rời bỏ **tính tại `reference_date`** |
| `risk_band` | CharField: `high` (≥ 0,6) · `medium` (≥ 0,3) · `low` | |
| ràng buộc | unique (`run`, `customer`) | |

### `SentimentLabel` (Tùng ghi khi nạp dữ liệu) và `SentimentResult` (Tùng ghi)
| Bảng | Trường |
|---|---|
| `SentimentLabel` | `interaction` (OneToOne `crm.InteractionLog`), `label` (`positive`·`neutral`·`negative`), `source` (tên bộ dữ liệu) |
| `SentimentResult` | `run` (FK, `related_name="sentiments"`), `interaction` (FK), `label`, `confidence` (Float, null), `latency_ms` (Int, null); unique (`run`, `interaction`) |

## 5. Tên phương pháp và khoá `metrics`

| Module | `method` | Khoá bắt buộc trong `metrics` | Chọn `is_selected` theo |
|---|---|---|---|
| forecast | `seasonal_naive`, `holt_winters`, `sarima` | `mae`, `rmse`, `mape` (%), `n_train`, `n_test` | `mape` nhỏ nhất |
| churn | `rfm_rule`, `logistic_regression`, `random_forest` | `auc`, `precision`, `recall`, `f1`, `accuracy`, `confusion_matrix` ([[tn, fp], [fn, tp]]), `churn_rate`, `n_train`, `n_test` | `auc` lớn nhất |
| sentiment | `keyword`, `gemini` | `accuracy`, `macro_f1`, `f1_by_class` ({positive, neutral, negative}), `confusion_matrix`, `n_eval`, `avg_latency_ms` | `macro_f1` lớn nhất |

Số thực làm tròn 4 chữ số. Tiền làm tròn đến đồng.

## 6. Quy ước code module AI

- File: `insights/pipeline/<module>.py`, mỗi file có hàm **`run(batch: str) -> list[ModelRun]`**.
- Đăng ký trong `insights/pipeline/__init__.py`: `MODULES = {"forecast": ..., "churn": ..., "sentiment": ...}`.
- Chạy: `python manage.py run_ai_pipeline` (tất cả) hoặc `--only forecast churn`. Lệnh tự xoá batch `demo` trước khi ghi.
- Mỗi phương pháp chạy trong `transaction.atomic()`; lỗi thì ghi `ModelRun(status="failed", notes=...)`, không làm dừng
  các phương pháp khác.
- Hằng số dùng chung đặt ở `insights/conf.py`: `CHURN_WINDOW_DAYS = 180`, `BACKTEST_MONTHS = 6`, `FORECAST_HORIZON = 6`,
  `RISK_HIGH = 0.6`, `RISK_MEDIUM = 0.3`, `RANDOM_STATE = 42`, `SENTIMENT_SAMPLE = 600` (0 = tất cả; mọi phương pháp
  cảm xúc chấm cùng tập mẫu này), hàm `reference_date()`.
- **Metrics phải tính lại được từ chính các dòng đã lưu của run** để lệnh `verify_ai_results` kiểm tra: dự báo tính trên
  các dòng `kind="backtest"`; cảm xúc tính trên toàn bộ `SentimentResult` của run. (Rời bỏ tính trên tập test không lưu
  từng dòng, nên chỉ kiểm tra tính hợp lệ, không tính lại.)
- Thư viện (đã ghim trong `requirements.txt`): `pandas`, `numpy`, `scikit-learn`, `statsmodels`, `openpyxl`.
- **Hàm dùng chung đã có sẵn – nên dùng, đừng viết lại:**
  - `insights.data.monthly_revenue_series()` → chuỗi doanh thu tháng đúng quy ước mục 3 (pandas Series, tần suất `MS`).
  - `insights.pipeline.base.run_method(batch, module, method, func)` → tạo `ModelRun`, chạy `func(run)` trong
    `transaction.atomic()`, bắt lỗi ghi `status="failed"`, làm tròn metrics. `func` ghi các dòng kết quả gắn với `run`
    và trả về `MethodResult(metrics=..., n_rows=..., params=..., notes=...)`.
  - `insights.pipeline.base.select_best(runs, metric, higher_is_better)` → đánh dấu đúng 1 `is_selected`.
  - `insights.conf.risk_band(probability)` → `high` / `medium` / `low` theo ngưỡng.
- **Dữ liệu thật có 24 tháng trọn vẹn** (12/2023 – 11/2025), ngày tham chiếu 09/12/2025.
- Test đặt ở `insights/tests/test_<module>.py`, dùng **dữ liệu giả nhỏ tự tạo trong test**, không phụ thuộc dữ liệu nạp.
  Toàn bộ `python manage.py test` phải qua trước khi mở Pull Request.

## 7. Schema `ai` – view cho Superset (Tùng tạo trong `sql/superset/03_ai_views.sql`)

Tất cả view chỉ lấy **batch thành công mới nhất** của từng module (trừ batch `demo` nếu đã có batch thật).

| View | Cột |
|---|---|
| `ai.model_run` | `batch`, `module`, `module_label`, `method`, `method_label`, `is_selected`, `finished_at`, `mae`, `rmse`, `mape`, `auc`, `precision`, `recall`, `f1`, `accuracy`, `macro_f1`, `n_train`, `n_test`, `avg_latency_ms`, `is_demo` |
| `ai.revenue_forecast` | `month`, `kind`, `kind_label`, `method`, `method_label`, `is_selected`, `actual`, `forecast`, `lower`, `upper`, `batch` |
| `ai.churn_score` | `customer_id`, `customer_name`, `customer_type`, `customer_source`, `staff_name`, `last_order_date`, `total_spent`, `method`, `method_label`, `is_selected`, `probability`, `risk_band`, `risk_label` (1. Cao / 2. Trung bình / 3. Thấp), `batch` |
| `ai.interaction_sentiment` | `interaction_id`, `interaction_date`, `channel`, `customer_name`, `method`, `method_label`, `is_selected`, `label_pred`, `label_true` (Tích cực/Trung lập/Tiêu cực), `is_correct`, `confidence`, `latency_ms`, `batch` |

Superset: kết nối **"SmartCRM TH2 (chỉ đọc)"**, 4 dataset trên đã có nhãn cột tiếng Việt và metric dùng chung
(`superset/bootstrap_th2.py`): `doanh_thu_thuc_te`, `doanh_thu_du_bao`, `can_duoi`, `can_tren`, `so_khach`, `rui_ro_tb`, `chi_tieu_rui_ro`, `so_cau`, `ti_le_dung`, `ti_le_tieu_cuc`.

## 8. Dashboard và biểu đồ

- Dashboard **"SmartCRM – AI Insights"**, slug **`smartcrm-ai-insights`**, 4 tab: **Tổng quan · Dự báo · Rời bỏ · Cảm xúc**.
- Tên biểu đồ có tiền tố tab: `[Tổng quan] …`, `[Dự báo] …`, `[Rời bỏ] …`, `[Cảm xúc] …`.
- Mọi biểu đồ chỉ đọc từ dataset trên schema `ai` (và `analytics` nếu cần), qua kết nối "SmartCRM TH2 (chỉ đọc)".

## 9. Tài liệu và báo cáo

| File | Người viết |
|---|---|
| `docs/th2/bao_cao/01_kien_truc.md` (kiến trúc, dữ liệu, bảo mật) | Tùng |
| `docs/th2/bao_cao/02_du_bao.md` | Ngọc Anh |
| `docs/th2/bao_cao/03_roi_bo.md` | Thái Anh |
| `docs/th2/bao_cao/04_cam_xuc.md` | Tùng |
| `docs/th2/bao_cao/05_mcp.md` (cài đặt MCP, câu lệnh đã dùng, ảnh) | Tùng + Hoàng Anh |
| `docs/th2/bao_cao/06_dashboard.md` | Hoàng Anh |
| `docs/th2/bao_cao/07_de_xuat_mo_rong.md` | Tùng |
| `docs/th2/bao_cao/08_kiem_thu_doi_chieu.md` | Hoàng Hưng |
| `docs/TH2_BAO_CAO.md` (bản gộp cuối cùng) | Hoàng Hưng |

### Khung bắt buộc cho các mục đánh giá mô hình (02, 03, 04)
1. **Bài toán và câu hỏi kinh doanh** – mô hình trả lời câu hỏi gì, ai dùng.
2. **Dữ liệu** – nguồn, khoảng thời gian, số dòng, cách xử lý, cách tạo nhãn.
3. **Phương pháp** – mỗi phương pháp 2–4 câu, ghi tham số chính.
4. **Cách đánh giá** – chia tập thế nào, chỉ số nào, vì sao chọn chỉ số đó.
5. **Kết quả** – bảng so sánh các phương pháp, **số lấy từ `ai.model_run` của batch cuối**, ghi rõ mã batch.
6. **Kết luận** – phương pháp được chọn và lý do.
7. **Hạn chế** – trung thực về dữ liệu và mô hình.
8. **Cách chạy lại** – lệnh cụ thể.
