# TH2 – Cài đặt từ đầu trên máy mới

Làm lần lượt từ trên xuống. Lệnh viết cho **PowerShell trên Windows**, chạy trong thư mục `smartcrm/`. Mỗi bước có dòng
**"Đúng khi"** để tự kiểm tra trước khi sang bước sau.

## 0. Cần có sẵn
- Git, Python 3.13, Docker Desktop (đang chạy).
- Quyền đọc repo `tbill111/Wagtail-CMS`.

## 1. Lấy mã nguồn và tạo môi trường ảo

```powershell
git clone https://github.com/tbill111/Wagtail-CMS.git smartcrm
cd smartcrm
git checkout th2/main
python -m venv ..\venv
..\venv\Scripts\Activate.ps1      # bị chặn script: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
```
**Đúng khi:** `python -c "import pandas, sklearn, statsmodels, wagtail"` không báo lỗi.

## 2. File `.env`

```powershell
Copy-Item .env.example .env
```
Mở `.env` và điền. Mỗi máy **tự đặt mật khẩu riêng** (Docker, PostgreSQL, Superset đều chạy trên máy mình, không có mật
khẩu nào phải dùng chung); **không gửi file `.env` qua Zalo/GitHub**:

| Biến | Giá trị |
|---|---|
| `DB_ENGINE` | `postgres` |
| `DB_NAME` | `smartcrm_th2` |
| `DB_PASSWORD`, `SUPERSET_*_PASSWORD`, `SUPERSET_SECRET_KEY`, `SUPERSET_GUEST_TOKEN_SECRET` | chuỗi ngẫu nhiên dài, tự đặt trên máy mình |
| `SUPERSET_PORT` | `8088` (đổi nếu cổng đã bị chiếm) |
| `GEMINI_API_KEY` | chỉ Tùng cần (module cảm xúc); để trống thì chạy chế độ mô phỏng |

Tạo chuỗi ngẫu nhiên: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

## 3. Chạy PostgreSQL và Superset

```powershell
docker compose up -d db
docker compose build superset
docker compose --profile init run --rm superset-init     # chỉ lần đầu
docker compose up -d superset
```
**Đúng khi:** `docker compose ps` thấy `db` và `superset` đều *healthy*; mở được `http://localhost:<SUPERSET_PORT>`.

## 4. Tạo CSDL TH2 và bảng

```powershell
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE smartcrm_th2 OWNER \"$POSTGRES_USER\""'
python manage.py migrate
python manage.py createsuperuser
```
**Đúng khi:** `python manage.py showmigrations insights` hiện `[X] 0001_initial`.

## 5. Tải và nạp dữ liệu thật

Tải 3 file vào thư mục `data/th2/` (thư mục này không được commit):

| File | Tải từ |
|---|---|
| `online_retail_II.xlsx` | https://archive.ics.uci.edu/dataset/502/online+retail+ii → Download, giải nén |
| `vi_sentiment_train.csv` | https://huggingface.co/datasets/anotherpolarbear/vietnamese-sentiment-analysis/resolve/main/train.csv |
| `vi_sentiment_test.csv` | https://huggingface.co/datasets/anotherpolarbear/vietnamese-sentiment-analysis/resolve/main/test.csv |

```powershell
python manage.py import_th2_data --retail data/th2/online_retail_II.xlsx `
    --reviews data/th2/vi_sentiment_train.csv data/th2/vi_sentiment_test.csv
```
Lần đầu mất khoảng 2 phút (đọc file Excel). **Đúng khi** dòng cuối in ra:
`Đã nạp 2000 khách, 14680 đơn (2370 đơn huỷ), 255715 dòng sản phẩm, 4424 sản phẩm, 3000 nhận xét có nhãn.` và
`Doanh thu đơn Hoàn thành: 186,513,155,070 VNĐ`. Máy nào ra số khác là đã có bước sai – báo Tùng.

Nạp lại từ đầu: thêm `--clear`.

## 6. Tầng view cho Superset

```powershell
docker compose exec db psql -U smartcrm -d smartcrm_th2 -v ON_ERROR_STOP=1 -f /sql/01_analytics_views.sql
docker compose exec db sh -c 'psql -U smartcrm -d smartcrm_th2 -v ON_ERROR_STOP=1 -v ro_password="$SUPERSET_RO_PASSWORD" -f /sql/02_superset_readonly_user.sql'
python manage.py seed_ai_demo                           # kết quả AI giả, để dựng dashboard trước
docker compose exec db psql -U smartcrm -d smartcrm_th2 -v ON_ERROR_STOP=1 -f /sql/03_ai_views.sql
```
**Đúng khi:** bảng kiểm tra cuối mỗi file đều `OK`.
> Dùng **Git Bash** thay PowerShell thì đặt `export MSYS_NO_PATHCONV=1` trước, nếu không đường dẫn `/sql/...` bị đổi
> thành đường dẫn Windows và báo "No such file".

## 7. Kết nối Superset và dataset

```powershell
python superset/bootstrap_th2.py
```
**Đúng khi:** in ra kết nối "SmartCRM TH2 (chỉ đọc)", 4 dataset `ai.model_run`, `ai.revenue_forecast`,
`ai.churn_score`, `ai.interaction_sentiment`, và dashboard `smartcrm-ai-insights` đã bật nhúng.
Lần đầu script tạo **khung** dashboard (tab Tổng quan, gồm các biểu đồ tên bắt đầu bằng `[Tổng quan]` nếu đã có);
chạy lại không đụng vào bố cục dashboard.

## 8. Chạy mô hình AI, kiểm tra và dashboard

```powershell
python manage.py run_ai_pipeline                        # tất cả module (cảm xúc gọi AI: vài phút)
python manage.py run_ai_pipeline --only forecast churn  # chỉ một số module
python manage.py verify_ai_results                      # đối chiếu kết quả – phải "Tất cả … mục KHỚP"
python manage.py test                                   # toàn bộ test phải OK
```
View `ai.*` tự lấy batch mới nhất, không cần chạy lại file 03. **Đúng khi:** `verify_ai_results` in
"Tất cả 40 mục KHỚP" (có `GEMINI_API_KEY`; không có key thì module cảm xúc chạy chế độ mô phỏng).

Dashboard: tab **Tổng quan** (4 biểu đồ `[Tổng quan] …`) do bước 7 tạo. Ba tab **Dự báo · Rời bỏ · Cảm xúc** dựng qua
Superset MCP theo `docs/th2/prompts/04_hoang_anh_dashboard.md` (danh sách biểu đồ và cách kiểm tra số liệu), hoặc
**Import** file xuất dashboard của nhóm trong Superset → Dashboards → Import.

## 9. Chạy web SmartCRM

```powershell
python manage.py runserver
```
Mở http://127.0.0.1:8000/admin/ (menu **Kết quả AI** xem các lần chạy mô hình), http://127.0.0.1:8000/crm/ và
http://127.0.0.1:8000/crm/analytics/ (tab **AI Insights** là dashboard TH2 nhúng trong SmartCRM).

## Lỗi hay gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `CSDL hiện tại là 'smartcrm'` khi nạp dữ liệu | `.env` chưa đặt `DB_NAME=smartcrm_th2` |
| `CSDL đã có khách hàng` | thêm `--clear` |
| `No such file` với `/sql/...` trong Git Bash | `export MSYS_NO_PATHCONV=1` |
| `relation "ai.model_run" does not exist` | chưa chạy file 03 (bước 6) |
| Superset không thấy kết nối TH2 | chạy lại bước 7; kiểm tra `SUPERSET_RO_PASSWORD` giống lúc chạy file 02 |
| Django báo `connection timeout expired` | Docker Desktop chưa chạy (thường sau khi khởi động lại máy) – mở Docker, chờ `docker ps` thấy `smartcrm-db-1 (healthy)` |
| Sửa code xong trình duyệt vẫn thấy giao diện cũ | còn tiến trình `runserver` cũ giữ cổng 8000 – tắt hết rồi chạy lại |
| `verify_ai_results` báo "Chỉ có dữ liệu giả" | chưa chạy `run_ai_pipeline` cho module đó (bước 8) |
| Biểu đồ Superset báo *Custom SQL fields cannot contain sub-queries* | Superset chặn truy vấn con trong bộ lọc tự viết – dùng metric tổng hợp, ví dụ `(ARRAY_AGG(forecast ORDER BY month))[1]` |
