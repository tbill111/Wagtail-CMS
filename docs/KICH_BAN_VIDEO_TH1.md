# Kịch bản video TH1 – Tích hợp Wagtail ERP/CRM với Apache Superset

**Người thực hiện:** Giang Thanh Tùng – 2351160563 · **Thời lượng:** khoảng 10 phút · **Giới hạn file:** 101 MB (MP4)

Bố cục màn hình suốt video:

```
┌──────────────── 1/3 ────────────────┬────────────────────── 2/3 ──────────────────────┐
│ ĐỀ BÀI (trang nhiệm vụ TH1)          │ THAO TÁC                                         │
│ – bôi đen / trỏ chuột vào đúng mục    │ VS Code · PowerShell · Superset · Wagtail         │
│   checklist đang trình bày            │                                                  │
└──────────────────────────────────────┴──────────────────────────────────────────────────┘
```

---

## A. Chuẩn bị trước khi bấm quay (không quay)

| # | Việc | Lệnh / thao tác |
|---|---|---|
| 1 | Bật Docker Desktop, chạy CSDL + Superset | `docker compose up -d db superset` (trong `smartcrm/`) |
| 2 | ~~Tạo tài khoản admin Wagtail trên PostgreSQL~~ – **đã có** `admin` (cùng mật khẩu với bài nhóm) | – |
| 3 | Chạy Wagtail | `python manage.py runserver` (để ở một terminal riêng) |
| 4 | Mở sẵn các tab trình duyệt (bên phải) | xem bảng **Link** bên dưới |
| 5 | Mở sẵn VS Code với các file cần show (xem từng mục) | phóng chữ lên 16–18 cho dễ đọc |
| 6 | Mở một terminal PowerShell ở `smartcrm/`, đã kích hoạt venv | `..\venv\Scripts\Activate.ps1` |
| 7 | **Không mở file `.env`** (có mật khẩu). Khi cần, mở `.env.example` | – |
| 8 | Chia màn hình: trang đề bài 1/3 bên trái, cửa sổ làm việc 2/3 bên phải | Windows: `Win + Z` → chọn bố cục 1/3 – 2/3 |
| 9 | Diễn tập 1 lần. Nếu đã tạo biểu đồ tay khi diễn tập thì xoá đi | Superset → Charts → xoá biểu đồ tập |

**Link dùng trong video**

| Tên | Link |
|---|---|
| Superset – đăng nhập | http://localhost:8090/login/ |
| Dashboard | http://localhost:8090/superset/dashboard/smartcrm-th1/ |
| Superset – kết nối CSDL | http://localhost:8090/databaseview/list/ |
| Superset – Datasets | http://localhost:8090/tablemodelview/list/ |
| Superset – SQL Lab | http://localhost:8090/sqllab/ |
| Superset – Charts (danh sách) | http://localhost:8090/chart/list/ |
| Superset – tạo biểu đồ mới | http://localhost:8090/chart/add |
| Wagtail – trang Tổng quan CRM | http://127.0.0.1:8000/crm/ |
| Wagtail Admin | http://127.0.0.1:8000/admin/ |

**Thiết lập OBS để file dưới 101 MB:** 1920×1080, 30 fps, x264, bitrate video **850 kbps**, âm thanh AAC **96 kbps**. 12 phút cho ra khoảng 85 MB.
Nếu quay chất lượng cao rồi mới nén, dùng: `ffmpeg -i goc.mp4 -c:v libx264 -preset slow -b:v 850k -c:a aac -b:a 96k TH1_GiangThanhTung_2351160563.mp4`

---

## B. Dòng thời gian

| Thời gian | Phần | Bên trái (đề bài) | Bên phải (thao tác chính) |
|---|---|---|---|
| 0:00 – 0:45 | Mở đầu | Tiêu đề + mô tả nhiệm vụ | Trang Tổng quan Wagtail `/crm/` → dashboard Superset |
| 0:45 – 2:00 | **01** CSDL + dữ liệu mẫu | Bôi đen mục 01 | `base.py`, `seed_superset.py`, bảng VERIFY của SQL view, Wagtail Admin |
| 2:00 – 3:00 | **02** Cài Superset bằng Docker | Mục 02 | `docker-compose.yml`, `superset_config.py`, `docker compose ps` + đăng nhập |
| 3:00 – 4:45 | **03** Kết nối qua SQLAlchemy URI | Mục 03 | File SQL 02, Database Connection, Test connection, SQL Lab |
| 4:45 – 7:00 | **04** Dataset + biểu đồ | Mục 04 | Trang Tổng quan bài nhóm, dataset/metric, tạo tay 1 biểu đồ, danh sách Charts |
| 7:00 – 9:00 | **05** Dashboard + kiểm tra số liệu | Mục 05 | Trang Tổng quan bài nhóm, dashboard + bộ lọc, `verify_superset_data` |
| 9:00 – 10:00 | Kết luận | Mô tả "bảo mật" trong đề | Tóm tắt bảo mật + 3 nhận định kinh doanh |

---

## C. Chi tiết từng phần

### 0:00 – 0:45 · Mở đầu
**Bên trái:** trỏ chuột vào tiêu đề và mô tả nhiệm vụ TH1.

**Chuẩn bị tab (trước khi bấm quay):** trong cửa sổ trình duyệt bên phải, xếp 2 tab đầu tiên theo đúng thứ tự, cả hai đã đăng nhập sẵn:
- **Tab 1** – Wagtail, trang Tổng quan CRM: http://127.0.0.1:8000/crm/
- **Tab 2** – Superset, dashboard: http://localhost:8090/superset/dashboard/smartcrm-th1/

Bắt đầu quay khi đang đứng ở **Tab 1**, cuộn lên đầu trang.

| Bước | Thời gian | Thao tác | Lời thoại |
|---|---|---|---|
| 1 | 0:00 – 0:12 | Đứng ở **Tab 1** (`/crm/`), để yên, không cuộn | "Em là Giang Thanh Tùng, MSSV 2351160563. Bài TH1 tích hợp hệ thống SmartCRM xây trên Wagtail, đóng vai trò ERP/CRM, với Apache Superset để làm dashboard phân tích kinh doanh." |
| 2 | 0:12 – 0:25 | Vẫn ở **Tab 1**, cuộn chậm xuống hết trang Tổng quan rồi dừng | "Đây là SmartCRM. Nhân viên nhập khách hàng, đơn hàng trong Wagtail, dữ liệu ghi vào PostgreSQL. Em tạo một schema `analytics` gồm các view đã ẩn email và số điện thoại." |
| 3 | 0:25 – 0:40 | Bấm `Ctrl + 2` để sang **Tab 2** (dashboard). Chờ biểu đồ tải xong rồi cuộn chậm một lượt từ KPI xuống hết, sau đó cuộn về đầu trang | "Superset kết nối vào schema đó bằng tài khoản chỉ đọc `superset_ro` qua SQLAlchemy URI, rồi dựng dashboard này." |
| 4 | 0:40 – 0:45 | Dừng ở đầu dashboard, trỏ chuột sang đề bài bên trái | "Em sẽ trình bày lần lượt 5 mục checklist." |

> **Chuyển tab:** `Ctrl + 1` về Tab 1, `Ctrl + 2` sang Tab 2 (hoặc `Ctrl + Tab` để sang tab kế bên). Bấm vào cửa sổ trình duyệt một lần trước khi dùng phím tắt, vì nếu con trỏ đang ở cửa sổ đề bài bên trái thì phím tắt sẽ đổi tab bên đó. Không chắc tay thì bấm chuột thẳng vào tab.
> Nếu Tab 2 hiện trang đăng nhập thay vì dashboard nghĩa là phiên Superset đã hết hạn: dừng quay, đăng nhập lại rồi quay lại phần này.

---

### 0:45 – 2:00 · Checklist 01 – CSDL Wagtail và dữ liệu mẫu
**Bên trái:** bôi đen dòng *01 Thiết lập cơ sở dữ liệu…*

| Bước | Thao tác | Lời thoại chính |
|---|---|---|
| 1 | VS Code: `smartcrm/settings/base.py` **dòng 101–115** | "Wagtail mặc định dùng SQLite. Em chuyển sang PostgreSQL qua biến `DB_ENGINE`, vì Superset chặn kết nối SQLite. Tên CSDL, tài khoản, mật khẩu đều đọc từ file `.env`, không ghi trong mã nguồn." |
| 2 | `crm/management/commands/seed_superset.py` **dòng 45–60** (`SOURCES` → `SEASONALITY`, nằm gọn trong một màn hình) | "Dữ liệu mẫu em sinh bằng lệnh `seed_superset` với seed riêng 2351160563: 150 khách, 431 đơn trong 18 tháng. Dữ liệu có kịch bản kinh doanh: 4 nguồn khách với tỉ trọng khác nhau, doanh thu tăng dịp Tết và cuối năm." (**Không chạy lại `--reset` khi quay**: chạy vào ngày khác sẽ ra bộ số khác.) |
| 3 | Terminal: `docker compose exec db psql -U smartcrm -d smartcrm -v ON_ERROR_STOP=1 -f /sql/01_analytics_views.sql` | Trong lúc lệnh chạy: "File SQL này tạo schema `analytics` gồm 7 view cho Superset: doanh thu chỉ tính đơn Hoàn thành, giờ Việt Nam, và bỏ email, số điện thoại." Chỉ vào bảng VERIFY: "7 dòng đều OK: 697 dòng sản phẩm, 431 đơn, 160 khách và doanh thu 2.291.030.000 đ khớp với bảng gốc." |
| 4 | Trình duyệt: http://127.0.0.1:8000/admin/ → *Khách hàng* → *Đơn hàng* (mở 1 đơn bất kỳ) | "Đây là ba tập dữ liệu mẫu đề yêu cầu, nằm ngay trong Wagtail Admin: khách hàng, đơn hàng, và doanh thu từ các dòng sản phẩm trong đơn." |

---

### 2:00 – 3:00 · Checklist 02 – Cài và cấu hình Superset bằng Docker
**Bên trái:** bôi đen dòng *02*.

| Bước | Thao tác | Lời thoại chính |
|---|---|---|
| 1 | `docker-compose.yml`: cuộn một lượt từ **dòng 11** tới **dòng 63** (`db` → `superset` → `superset-init`) | "Em cài bằng Docker Compose với 3 dịch vụ: PostgreSQL 16, Superset 4.1.2 build từ `superset/Dockerfile` có cài thêm driver `psycopg2`, và `superset-init` chạy một lần để tạo metadata và tài khoản admin. Cổng chỉ mở trên `127.0.0.1`; thiếu mật khẩu trong `.env` thì Docker dừng ngay." |
| 2 | `superset/superset_config.py` (cả file vừa một màn hình) | "Phần cấu hình: SECRET_KEY lấy từ biến môi trường, metadata Superset để ở CSDL riêng `superset_meta`, chặn kết nối không an toàn và giới hạn 10.000 dòng mỗi truy vấn." |
| 3 | Terminal: `docker compose ps` → trình duyệt: Superset **Settings → Logout**, đăng nhập lại ở http://localhost:8090/login/ | "Cả 2 container đều *healthy*: db ở cổng 5435, Superset ở cổng 8090. Superset đã chạy và đăng nhập được." |

---

### 3:00 – 4:45 · Checklist 03 – Kết nối qua SQLAlchemy URI
**Bên trái:** bôi đen dòng *03*.

| Bước | Thao tác | Lời thoại chính |
|---|---|---|
| 1 | `sql/superset/02_superset_readonly_user.sql` **dòng 22–39** | "Em tạo tài khoản `superset_ro` theo nguyên tắc quyền tối thiểu: chỉ SELECT trên schema `analytics`, phiên luôn read-only, mỗi truy vấn tối đa 30 giây, tối đa 10 kết nối." |
| 2 | Terminal: `docker compose exec db sh -c 'psql -U smartcrm -d smartcrm -v ON_ERROR_STOP=1 -v ro_password="$SUPERSET_RO_PASSWORD" -f /sql/02_superset_readonly_user.sql'` | "Bảng VERIFY: không đọc được bảng gốc, đọc được 7 view, không ghi được. Tất cả OK." |
| 3 | Superset → **Settings → Database Connections** → sửa *SmartCRM – Wagtail (chỉ đọc)* | Chỉ vào URI `postgresql+psycopg2://superset_ro:XXXXXXXXXX@db:5432/smartcrm`: "Đây là SQLAlchemy URI. Host là `db`, tên dịch vụ trong mạng Docker; cổng 5432 là cổng bên trong container. Mật khẩu được Superset che đi." |
| 4 | Bấm **Test connection** | "Connection looks good." |
| 5 | Tab **Advanced → SQL Lab** | "*Allow DML* đang tắt, nên không chạy được INSERT/UPDATE/DELETE." |
| 6 | SQL Lab: `SELECT * FROM public.crm_customer LIMIT 5;` | Báo lỗi *permission denied for schema public*: "Superset không đọc được bảng gốc có email/SĐT." |
| 7 | SQL Lab: `SELECT customer_name, rfm_segment, monetary FROM analytics.v_customer_rfm LIMIT 10;` | "Còn view phân tích thì đọc bình thường." |
| 8 | *(Tuỳ chọn)* `superset/bootstrap_dashboard.py` **dòng 264–272** | "Script của em cũng tạo đúng kết nối này qua REST API, với `allow_dml` tắt." |

> Nếu muốn tạo mới bằng tay: **+ Database → PostgreSQL → Connect this database with a SQLAlchemy URI string instead**. Gõ mật khẩu thật vào URI xong thì **cắt đoạn đó khi dựng video**.

---

### 4:45 – 7:00 · Checklist 04 – Dataset và biểu đồ theo nghiệp vụ CRM
**Bên trái:** bôi đen dòng *04*.

| Bước | Thao tác | Lời thoại chính |
|---|---|---|
| 1 | **Phần có sẵn của bài nhóm:** `Ctrl + 1` về Tab 1 (http://127.0.0.1:8000/crm/), cuộn qua các biểu đồ của trang Tổng quan | "Trước hết là phần đã có sẵn. Bài nhóm của em có trang Tổng quan này, gồm doanh thu 12 tháng, khách hàng theo trạng thái, top khách hàng và top sản phẩm. Các số liệu này tính bằng Python ngay trong Wagtail, nên chỉ xem được cố định, không lọc hay đào sâu được. Ở TH1 em đưa dữ liệu sang Superset để khám phá và phân tích linh hoạt hơn." |
| 2 | **Khám phá dữ liệu (Dataset):** Superset → **Datasets** (http://localhost:8090/tablemodelview/list/) → rê chuột vào `v_order_lines` → cây bút (Edit) → tab **Metrics**. Xong bấm Cancel | "Đây là các dataset em tạo trong Superset từ cơ sở dữ liệu của Wagtail. Em mở dataset chính là `v_order_lines`: mỗi dòng là một sản phẩm trong một đơn hàng, kèm ngày đặt, khách hàng, nguồn khách, nhóm sản phẩm và nhân viên phụ trách. Trên dataset em định nghĩa sẵn các chỉ số nghiệp vụ: doanh thu, số đơn hoàn thành, giá trị đơn trung bình, số lượng bán và tỉ lệ huỷ. Doanh thu chỉ tính đơn Hoàn thành, đúng công thức của bài nhóm, nên số liệu hai bên đối chiếu được." |
| 3 | **Tạo biểu đồ (Chart):** Charts → **+ Chart** (http://localhost:8090/chart/add) → dataset `v_customer_rfm` → **Pie Chart** → Dimension `rfm_segment`, Metric `so_khach_rfm` → **Update chart** → Save tên *"Cơ cấu khách hàng theo phân khúc RFM"* (**không** thêm vào dashboard `smartcrm-th1`) | Trong lúc thao tác: "Bây giờ em tạo trực tiếp một biểu đồ. Yêu cầu nghiệp vụ CRM ở đây là: khách hàng của mình đang phân bố thế nào, nhóm nào cần chăm sóc trước? Em chọn dataset phân khúc RFM, loại biểu đồ tròn, chia theo phân khúc và đếm số khách." Khi biểu đồ hiện ra: "Kết quả cho thấy trong 87 khách đã mua, nhóm Có nguy cơ rời bỏ và Ngủ đông cộng lại là 36 khách, tức hơn 40%. Đây là phân tích bài nhóm chưa có." |
| 4 | **Các biểu đồ còn lại:** Superset → **Charts** (http://localhost:8090/chart/list/), cuộn một lượt | "Các biểu đồ còn lại em dựng theo cùng cách, mỗi biểu đồ trả lời một câu hỏi nghiệp vụ CRM: doanh thu theo tháng để thấy mùa vụ, cơ cấu theo nguồn khách để biết kênh marketing nào hiệu quả, top sản phẩm để biết nên nhập gì, doanh thu theo nhân viên để đánh giá đội kinh doanh, và tồn kho để cảnh báo sắp hết hàng. Nhóm biểu đồ này mở rộng từ trang Tổng quan của bài nhóm. Còn phân khúc RFM, tỉ lệ rời bỏ theo nguồn khách và cohort giữ chân khách là phần em bổ sung riêng." |

---

### 7:00 – 9:00 · Checklist 05 – Dashboard tổng hợp và kiểm tra tính chính xác
**Bên trái:** bôi đen dòng *05*.

| Bước | Thao tác | Lời thoại chính |
|---|---|---|
| 1 | **Phần có sẵn của bài nhóm:** `Ctrl + 1` về Tab 1 (http://127.0.0.1:8000/crm/). Chỉ chuột vào *Doanh thu 12 tháng*, *Top khách hàng*, *Sản phẩm sắp hết hàng* | "Trước khi vào dashboard, em nhắc lại phần đã có sẵn. Bài nhóm của em có trang Tổng quan này trong Wagtail, gồm doanh thu 12 tháng gần nhất, top khách hàng theo chi tiêu, top sản phẩm bán chạy và danh sách sản phẩm sắp hết hàng. Các số này tính bằng Python trực tiếp trên bảng gốc, nên em coi đây là số liệu chuẩn của hệ thống CRM. Ví dụ tháng 1 năm 2026 doanh thu khoảng 250 triệu, khách chi tiêu nhiều nhất là Trần Thu Dũng với 123 triệu 4. Lát nữa em dùng chính các số này để kiểm tra dashboard của mình." |
| 2 | **Phần riêng – dashboard tổng hợp:** `Ctrl + 2` sang http://localhost:8090/superset/dashboard/smartcrm-th1/. Cuộn chậm một lượt từ KPI xuống hết rồi về đầu trang. Chọn bộ lọc **Nguồn khách = Website** → *Apply* → *Clear all* | Khi cuộn: "Còn đây là dashboard tổng hợp em thiết kế trên Superset cho bài TH1. Hàng trên cùng là 4 chỉ số chính: tổng doanh thu 2,29 tỷ, 359 đơn hoàn thành, giá trị đơn trung bình 6,38 triệu và tỉ lệ huỷ 12,3%. Bên dưới là 9 biểu đồ kinh doanh: doanh thu theo tháng với đỉnh vào tháng 1 dịp Tết, cơ cấu theo nguồn khách, theo nhóm sản phẩm, top sản phẩm, doanh thu theo nhân viên, khách hàng theo trạng thái, tương tác theo kênh, top khách hàng và tồn kho. Cuối trang là 5 biểu đồ phân tích bổ sung của em về RFM, tỉ lệ rời bỏ và cohort. Tháng 10 đang bằng 0 vì tháng mới bắt đầu, chưa có đơn nào hoàn thành." Khi lọc: "Khác với trang Tổng quan của nhóm chỉ xem được cố định, dashboard này lọc được theo thời gian, nguồn khách, nhóm khách và nhóm sản phẩm. Em thử lọc riêng kênh Website, các chỉ số và biểu đồ doanh thu đổi theo ngay." Khi bỏ lọc: "Đối chiếu với trang của nhóm vừa xem: tháng 1 năm 2026 cũng khoảng 250 triệu, khách đứng đầu cũng là Trần Thu Dũng với 123 triệu 4. Hai bên khớp nhau." |
| 3 | **Kiểm tra tự động:** Terminal: `python manage.py verify_superset_data --superset` | Trong lúc lệnh chạy: "So bằng mắt thì chưa đủ, nên em kiểm tra tiếp bằng lệnh tự động. Lệnh này em viết riêng cho TH1. Nó lấy 12 chỉ số, gồm tổng doanh thu, số đơn, tỉ lệ huỷ, doanh thu từng tháng, top khách, top sản phẩm, tồn kho, RFM, tỉ lệ rời bỏ và cohort, rồi so theo 3 nguồn độc lập: các hàm thống kê của bài nhóm, view PostgreSQL em viết, và cùng câu SQL nhưng chạy qua Superset bằng tài khoản chỉ đọc." Khi kết quả hiện ra: "Cả 12 chỉ số đều KHỚP ở cả ba nguồn. Như vậy số liệu hiển thị trên dashboard là chính xác so với dữ liệu gốc trong Wagtail." |


---

### 9:00 – 10:00 · Kết luận
**Bên trái:** bôi đen câu *"đảm bảo luồng dữ liệu thông suốt và bảo mật trong quá trình kết nối"*.

**Thao tác (chỉ dùng trình duyệt, không mở VS Code):** ở dashboard http://localhost:8090/superset/dashboard/smartcrm-th1/
1. Đầu trang, khối *Nguồn dữ liệu* – nói câu tóm tắt và phần bảo mật.
2. Cuộn xuống bảng *Phân khúc khách hàng RFM* – nhận định 1.
3. Cuộn lên *Cơ cấu doanh thu theo nguồn khách*, rồi xuống *Tỉ lệ rời bỏ theo nguồn khách* – nhận định 2.
4. Biểu đồ *Giá trị đơn trung bình theo nhóm khách* (ngay bên cạnh) – nhận định 3.

**Lời thoại:**
> "Tóm lại, nhóm em xây hệ thống SmartCRM trên Wagtail để quản lý khách hàng, đơn hàng, tồn kho và hỗ trợ AI. Ở bài TH1 này em phát triển tiếp phần phân tích: chuyển sang PostgreSQL, sinh dữ liệu mẫu, viết tầng view, kết nối Superset bằng tài khoản chỉ đọc và dựng dashboard.
> Về bảo mật: mật khẩu chỉ nằm trong `.env`; Superset dùng tài khoản chỉ đọc, không thấy email/SĐT, không ghi được dữ liệu; truy vấn bị giới hạn thời gian; cổng chỉ mở trên máy mình.
> Ba nhận định từ dữ liệu:
> 1. 11 khách VIP tạo 23% doanh thu, nhưng nhóm *Có nguy cơ rời bỏ* (19 khách, trung bình khoảng 186 ngày chưa mua – đọc số trên bảng RFM lúc quay, mỗi ngày tăng 1) đang giữ 35% doanh thu. Cần chăm sóc lại nhóm này trước tiên.
> 2. Website là kênh tốt nhất: 38,8% doanh thu và tỉ lệ rời bỏ thấp nhất (13%). Kênh *Khác* rời bỏ tới 50%.
> 3. Đơn của doanh nghiệp trung bình 9,47 triệu, gấp đôi khách cá nhân/cửa hàng (4,54 triệu), nên ưu tiên các gói phần mềm và dịch vụ cho doanh nghiệp.
> Em xin cảm ơn."

---

## D. Mẹo khi quay
- Mỗi khi chuyển checklist, **bôi đen dòng tương ứng bên trái** trước rồi mới thao tác bên phải. Giảng viên sẽ thấy rõ bạn đang chấm mục nào.
- Gõ sẵn các lệnh dài vào một file nháp để copy, tránh gõ sai khi quay.
- Lệnh chạy lâu (verify) thì nói tiếp phần giải thích trong lúc chờ.
- Phóng to vừa đủ: Superset zoom 80–90%, VS Code chữ 16–18.
