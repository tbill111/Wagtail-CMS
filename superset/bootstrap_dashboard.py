"""Dựng sẵn kết nối, dataset, biểu đồ và dashboard SmartCRM trên Apache Superset qua REST API (TH1).

    python superset/bootstrap_dashboard.py            # tạo mới; bỏ qua nếu dashboard đã có
    python superset/bootstrap_dashboard.py --force    # xoá dashboard + biểu đồ cũ rồi dựng lại

Lần chạy nào cũng bật chế độ nhúng (Embedded) cho dashboard để SmartCRM hiển thị tại /crm/analytics/;
dashboard đã có thì giữ nguyên biểu đồ, chỉ cập nhật danh sách địa chỉ được phép nhúng (SUPERSET_EMBED_ORIGINS).

Chạy trên máy (ngoài Docker) bằng venv của dự án, sau khi đã:
  1. chạy sql/superset/01_analytics_views.sql và 02_superset_readonly_user.sql
  2. `docker compose up -d superset`
Đọc cấu hình từ .env: SUPERSET_PORT, SUPERSET_ADMIN_USER/PASSWORD, SUPERSET_RO_PASSWORD, DB_NAME,
và thông tin cá nhân STUDENT_NAME, STUDENT_ID, TH1_SEED (hiện trên tiêu đề + khối giới thiệu dashboard).

Các bước tương ứng checklist:
  03 – tạo Database connection qua SQLAlchemy URI, dùng tài khoản chỉ đọc superset_ro
  04 – đăng ký 7 dataset (view trong schema analytics) + metric dùng chung, tạo các biểu đồ
       (kể cả phần phân tích bổ sung: phân khúc RFM, tỉ lệ rời bỏ theo nguồn, cohort giữ chân khách)
  05 – ghép thành dashboard "SmartCRM – Phân tích kinh doanh" kèm bộ lọc
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SUPERSET_URL = f"http://127.0.0.1:{os.getenv('SUPERSET_PORT', '8088')}"
DATABASE_NAME = "SmartCRM – Wagtail (chỉ đọc)"
SCHEMA = "analytics"
DASHBOARD_SLUG = "smartcrm-th1"
STUDENT_NAME = os.getenv("STUDENT_NAME", "").strip()
STUDENT_ID = os.getenv("STUDENT_ID", "").strip()
TH1_SEED = os.getenv("TH1_SEED", "").strip()
AUTHOR = " – ".join(part for part in (STUDENT_NAME, STUDENT_ID) if part)
DASHBOARD_TITLE = "SmartCRM – Phân tích kinh doanh" + (f" ({AUTHOR})" if AUTHOR else "")
VND = ",d"
EMBED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("SUPERSET_EMBED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
    if origin.strip()
]

# Dataset: view -> (cột thời gian chính, {cột: tên hiển thị}, [metric dùng chung])
DATASETS = {
    "v_order_lines": ("order_date", {
        "order_code": "Mã đơn", "order_date": "Ngày đặt", "order_status_label": "Trạng thái đơn",
        "customer_name": "Khách hàng", "customer_type": "Nhóm khách", "customer_source": "Nguồn khách",
        "staff_name": "Nhân viên phụ trách", "product_sku": "SKU", "product_name": "Sản phẩm",
        "product_group": "Nhóm sản phẩm", "quantity": "Số lượng", "unit_price": "Đơn giá", "line_total": "Thành tiền",
    }, [
        ("doanh_thu", "Doanh thu (VNĐ)", "SUM(CASE WHEN is_completed THEN line_total ELSE 0 END)", VND),
        ("so_don_hoan_thanh", "Số đơn hoàn thành", "COUNT(DISTINCT CASE WHEN is_completed THEN order_id END)", ",d"),
        ("gia_tri_don_tb", "Giá trị đơn trung bình (VNĐ)",
         "SUM(CASE WHEN is_completed THEN line_total ELSE 0 END) / "
         "NULLIF(COUNT(DISTINCT CASE WHEN is_completed THEN order_id END), 0)", VND),
        ("so_luong_ban", "Số lượng bán", "SUM(CASE WHEN is_completed THEN quantity ELSE 0 END)", ",d"),
        ("ti_le_huy", "Tỉ lệ đơn huỷ",
         "COUNT(DISTINCT CASE WHEN order_status = 'cancelled' THEN order_id END)::numeric / "
         "NULLIF(COUNT(DISTINCT order_id), 0)", ".1%"),
    ]),
    "v_customers": ("created_date", {
        "customer_name": "Khách hàng", "company": "Công ty", "customer_type": "Nhóm khách",
        "customer_status_label": "Trạng thái", "customer_source": "Nguồn khách", "ai_priority": "Ưu tiên (AI)",
        "ai_sentiment": "Cảm xúc (AI)", "staff_name": "Nhân viên phụ trách", "created_date": "Ngày tạo",
        "orders_count": "Số đơn", "completed_orders": "Đơn hoàn thành", "total_spent": "Tổng chi tiêu",
        "last_order_date": "Đơn gần nhất", "days_since_last_order": "Số ngày chưa mua",
        "interactions_count": "Số tương tác",
    }, [
        ("so_khach", "Số khách hàng", "COUNT(*)", ",d"),
        ("tong_chi_tieu", "Tổng chi tiêu (VNĐ)", "SUM(total_spent)", VND),
    ]),
    "v_products": (None, {
        "product_sku": "SKU", "product_name": "Sản phẩm", "product_group": "Nhóm sản phẩm", "unit": "Đơn vị",
        "price": "Giá bán", "stock": "Tồn kho", "min_stock": "Tồn tối thiểu", "is_low_stock": "Sắp hết hàng",
        "low_stock_label": "Sắp hết hàng", "sold_quantity": "Đã bán", "revenue": "Doanh thu",
    }, []),
    "v_interactions": ("interaction_date", {
        "interaction_date": "Thời gian", "channel": "Kênh", "customer_name": "Khách hàng",
        "is_ai_generated": "Có dùng AI", "is_answered": "Đã phản hồi", "staff_name": "Nhân viên",
    }, [
        ("so_tuong_tac", "Số tương tác", "COUNT(*)", ",d"),
        ("ti_le_dung_ai", "Tỉ lệ phản hồi dùng AI", "AVG(CASE WHEN is_ai_generated THEN 1.0 ELSE 0 END)", ".0%"),
        ("ti_le_phan_hoi", "Tỉ lệ đã phản hồi", "AVG(CASE WHEN is_answered THEN 1.0 ELSE 0 END)", ".0%"),
    ]),
    "v_orders": ("order_date", {
        "order_code": "Mã đơn", "order_date": "Ngày đặt", "order_status_label": "Trạng thái đơn",
        "customer_name": "Khách hàng", "customer_source": "Nguồn khách", "total_amount": "Giá trị đơn",
    }, [
        ("so_don", "Số đơn", "COUNT(*)", ",d"),
    ]),
    # ---- Phân tích bổ sung (cá nhân)
    "v_customer_rfm": (None, {
        "customer_name": "Khách hàng", "customer_type": "Nhóm khách", "customer_source": "Nguồn khách",
        "staff_name": "Nhân viên phụ trách", "customer_status_label": "Trạng thái",
        "recency_days": "Số ngày từ lần mua cuối", "frequency": "Số đơn hoàn thành", "monetary": "Tổng chi tiêu",
        "r_score": "Điểm R", "f_score": "Điểm F", "m_score": "Điểm M", "rfm_code": "Mã RFM",
        "rfm_segment": "Phân khúc RFM",
    }, [
        ("so_khach_rfm", "Số khách", "COUNT(*)", ",d"),
        ("chi_tieu_rfm", "Tổng chi tiêu (VNĐ)", "SUM(monetary)", VND),
        ("ti_trong_doanh_thu", "Tỉ trọng doanh thu", "SUM(monetary) / NULLIF(SUM(SUM(monetary)) OVER (), 0)", ".1%"),
        ("recency_tb", "Số ngày chưa mua (TB)", "AVG(recency_days)", ",.0f"),
        ("tan_suat_tb", "Số đơn / khách (TB)", "AVG(frequency)", ",.1f"),
    ]),
    "v_cohort": ("cohort_month", {
        "cohort_month": "Tháng mua đầu tiên", "cohort_label": "Cohort (tháng mua đầu)",
        "month_number": "Số tháng sau lần mua đầu", "active_customers": "Khách mua lại",
        "cohort_size": "Quy mô cohort", "retention_rate": "Tỉ lệ giữ chân",
    }, [
        ("ti_le_giu_chan", "Tỉ lệ giữ chân", "SUM(active_customers)::numeric / NULLIF(SUM(cohort_size), 0)", ".0%"),
    ]),
}

# Metric bổ sung cho dataset đã có (phân tích cá nhân)
DATASETS["v_customers"][2].append(
    ("ti_le_roi_bo", "Tỉ lệ rời bỏ",
     "COUNT(*) FILTER (WHERE customer_status = 'churned')::numeric / "
     "NULLIF(COUNT(*) FILTER (WHERE customer_status IN ('customer', 'churned')), 0)", ".1%"))


def kpi(metric, subheader):
    return {"viz_type": "big_number_total", "metric": metric, "subheader": subheader,
            "header_font_size": 0.4, "subheader_font_size": 0.15, "y_axis_format": "SMART_NUMBER"}


def timeseries(viz, metrics, groupby=(), **extra):
    return {"viz_type": viz, "x_axis": "order_date", "time_grain_sqla": "P1M", "metrics": metrics,
            "groupby": list(groupby), "row_limit": 10000, "y_axis_format": "SMART_NUMBER",
            "x_axis_time_format": "%m/%Y", "rich_tooltip": True, "show_legend": bool(groupby),
            "legendOrientation": "top", "truncate_metric": True, **extra}


def category_bar(x_axis, metrics, groupby=(), horizontal=False, **extra):
    return {"viz_type": "echarts_timeseries_bar", "x_axis": x_axis, "metrics": metrics, "groupby": list(groupby),
            "orientation": "horizontal" if horizontal else "vertical", "row_limit": 10000,
            "x_axis_sort_asc": False, "y_axis_format": "SMART_NUMBER", "show_legend": bool(groupby),
            "legendOrientation": "top", "rich_tooltip": True, "truncate_metric": True, "show_value": True,
            **extra}


# (khoá, tên biểu đồ, dataset, tham số, áp dụng bộ lọc thời gian/nguồn khách của dashboard?)
CHARTS = [
    ("kpi_revenue", "Tổng doanh thu", "v_order_lines", kpi("doanh_thu", "VNĐ – chỉ tính đơn Hoàn thành"), True),
    ("kpi_orders", "Số đơn hoàn thành", "v_order_lines", kpi("so_don_hoan_thanh", "đơn"), True),
    ("kpi_aov", "Giá trị đơn trung bình", "v_order_lines", kpi("gia_tri_don_tb", "VNĐ / đơn hoàn thành"), True),
    ("kpi_cancel", "Tỉ lệ đơn huỷ", "v_order_lines",
     {**kpi("ti_le_huy", "trên tổng số đơn"), "y_axis_format": ".1%"}, True),
    ("revenue_month", "Doanh thu theo tháng", "v_order_lines",
     timeseries("echarts_timeseries_line", ["doanh_thu"], markerEnabled=True, area=True, opacity=0.2), True),
    ("revenue_source", "Cơ cấu doanh thu theo nguồn khách", "v_order_lines",
     {"viz_type": "pie", "groupby": ["customer_source"], "metric": "doanh_thu", "donut": True,
      "show_labels": True, "labels_outside": False, "label_line": False, "label_type": "percent",
      "number_format": "SMART_NUMBER", "outerRadius": 65, "innerRadius": 35,
      "show_legend": True, "legendOrientation": "bottom", "legendType": "plain", "sort_by_metric": True,
      "row_limit": 100}, True),
    ("revenue_group_month", "Doanh thu theo nhóm sản phẩm từng tháng", "v_order_lines",
     timeseries("echarts_timeseries_bar", ["doanh_thu"], ["product_group"], stack="Stack"), True),
    ("top_products", "Top 10 sản phẩm bán chạy (số lượng)", "v_order_lines",
     category_bar("product_name", ["so_luong_ban"], horizontal=True, x_axis_sort="so_luong_ban",
                  row_limit=10, y_axis_format=",d"), True),
    ("revenue_staff", "Doanh thu theo nhân viên phụ trách", "v_order_lines",
     category_bar("staff_name", ["doanh_thu"], horizontal=True, x_axis_sort="doanh_thu"), True),
    ("customer_status", "Khách hàng theo trạng thái và mức ưu tiên (AI)", "v_customers",
     category_bar("customer_status_label", ["so_khach"], ["ai_priority"], stack="Stack",
                  x_axis_sort_asc=True, y_axis_format=",d"), False),
    ("top_customers", "Top 10 khách hàng theo tổng chi tiêu", "v_customers",
     {"viz_type": "table", "query_mode": "raw",
      "all_columns": ["customer_name", "customer_type", "customer_source", "staff_name",
                      "completed_orders", "total_spent", "last_order_date"],
      "order_by_cols": [json.dumps(["total_spent", False])], "row_limit": 10,
      "table_timestamp_format": "%d/%m/%Y", "show_cell_bars": True,
      "column_config": {"total_spent": {"d3NumberFormat": VND}}}, False),
    ("low_stock", "Tồn kho thiết bị & vật tư", "v_products",
     {"viz_type": "table", "query_mode": "raw",
      "all_columns": ["product_sku", "product_name", "stock", "min_stock", "low_stock_label", "sold_quantity"],
      "adhoc_filters": [{"expressionType": "SQL", "sqlExpression": "track_stock", "clause": "WHERE"}],
      "order_by_cols": [json.dumps(["stock", True])], "row_limit": 100, "show_cell_bars": True},
     False),
    ("interactions_channel", "Tương tác theo kênh & tỉ lệ dùng AI", "v_interactions",
     {"viz_type": "table", "query_mode": "aggregate", "groupby": ["channel"],
      "metrics": ["so_tuong_tac", "ti_le_phan_hoi", "ti_le_dung_ai"], "row_limit": 100,
      "order_desc": True, "timeseries_limit_metric": "so_tuong_tac", "show_cell_bars": True,
      "percent_metrics": []}, False),
    # ---- Phân tích bổ sung (cá nhân)
    ("rfm_segments", "Phân khúc khách hàng RFM", "v_customer_rfm",
     {"viz_type": "table", "query_mode": "aggregate", "groupby": ["rfm_segment"],
      "metrics": ["so_khach_rfm", "chi_tieu_rfm", "ti_trong_doanh_thu", "recency_tb", "tan_suat_tb"],
      "row_limit": 100, "order_desc": False,
      "timeseries_limit_metric": {"expressionType": "SQL", "sqlExpression": "MIN(rfm_segment)",
                                  "label": "thu_tu_phan_khuc"}, "show_cell_bars": True,
      "percent_metrics": []}, False),
    ("rfm_source", "Phân khúc RFM theo nguồn khách", "v_customer_rfm",
     category_bar("customer_source", ["so_khach_rfm"], ["rfm_segment"], stack="Stack",
                  x_axis_sort="so_khach_rfm", y_axis_format=",d", show_value=False, legendType="plain"), False),
    ("churn_source", "Tỉ lệ rời bỏ theo nguồn khách", "v_customers",
     category_bar("customer_source", ["ti_le_roi_bo"], x_axis_sort="ti_le_roi_bo", y_axis_format=".0%"), False),
    ("aov_type", "Giá trị đơn trung bình theo nhóm khách", "v_order_lines",
     category_bar("customer_type", ["gia_tri_don_tb"], x_axis_sort="gia_tri_don_tb"), True),
    ("cohort_heatmap", "Tỉ lệ khách quay lại mua theo tháng mua đầu tiên (cohort)", "v_cohort",
     {"viz_type": "heatmap", "all_columns_x": "month_number", "all_columns_y": "cohort_label",
      "metric": "ti_le_giu_chan",
      "adhoc_filters": [{"expressionType": "SQL", "sqlExpression": "month_number BETWEEN 1 AND 12",
                         "clause": "WHERE"}],
      "row_limit": 10000, "linear_color_scheme": "schemeBlues", "normalize_across": "heatmap",
      "canvas_image_rendering": "pixelated", "y_axis_bounds": [None, None],
      "show_legend": True, "show_values": True, "show_perc": False,
      "y_axis_format": ".0%", "sort_x_axis": "alpha_asc", "sort_y_axis": "alpha_asc",
      "xscale_interval": 1, "yscale_interval": 1, "left_margin": 70, "bottom_margin": "auto"}, False),
]

# Bố cục dashboard: mỗi hàng là danh sách (khoá biểu đồ, độ rộng /12, chiều cao)
LAYOUT = [
    [("kpi_revenue", 3, 22), ("kpi_orders", 3, 22), ("kpi_aov", 3, 22), ("kpi_cancel", 3, 22)],
    [("revenue_month", 8, 55), ("revenue_source", 4, 55)],
    [("revenue_group_month", 12, 55)],
    [("top_products", 6, 60), ("revenue_staff", 6, 60)],
    [("customer_status", 6, 60), ("interactions_channel", 6, 60)],
    [("top_customers", 7, 60), ("low_stock", 5, 60)],
    [("MARKDOWN-personal", 12, 16)],
    [("rfm_segments", 6, 55), ("rfm_source", 6, 55)],
    [("churn_source", 6, 50), ("aov_type", 6, 50)],
    [("cohort_heatmap", 12, 75)],
]

INTRO = """### Nguồn dữ liệu
CSDL PostgreSQL của **Wagtail CRM** → schema `analytics` (view chỉ đọc) → Superset kết nối bằng tài khoản
`superset_ro` (chỉ SELECT, không thấy email/SĐT khách hàng).
**Doanh thu** = Σ số lượng × đơn giá của đơn **Hoàn thành**, thời gian theo giờ Việt Nam –
cùng quy ước với trang Tổng quan `/crm/` nên số liệu đối chiếu được (`python manage.py verify_superset_data`)."""
if AUTHOR or TH1_SEED:
    INTRO += "\n\n**Người thực hiện:** " + (AUTHOR or "–") + (
        f" · Bộ dữ liệu riêng: `seed_superset --seed {TH1_SEED}`" if TH1_SEED else "")

PERSONAL = "### Phân tích bổ sung" + (f" – {STUDENT_NAME}" if STUDENT_NAME else "") + """
**RFM** chấm điểm 1–5 cho mỗi khách đã mua theo độ *gần đây* (R), *tần suất* (F), *giá trị* (M) để chia phân khúc
chăm sóc. **Tỉ lệ rời bỏ** = khách đã rời bỏ / khách từng mua. **Cohort**: trong số khách mua lần đầu ở tháng X,
bao nhiêu % quay lại mua sau 1, 2, 3… tháng."""
MARKDOWN = {"MARKDOWN-intro": INTRO, "MARKDOWN-personal": PERSONAL}


class Superset:
    def __init__(self, url, username, password):
        self.http = httpx.Client(base_url=url, timeout=60, follow_redirects=True)
        token = self.http.post("/api/v1/security/login", json={
            "username": username, "password": password, "provider": "db", "refresh": True,
        })
        token.raise_for_status()
        self.http.headers["Authorization"] = f"Bearer {token.json()['access_token']}"
        csrf = self.http.get("/api/v1/security/csrf_token/")
        csrf.raise_for_status()
        self.http.headers.update({"X-CSRFToken": csrf.json()["result"], "Referer": url})

    def call(self, method, path, **kwargs):
        response = self.http.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise SystemExit(f"Lỗi {response.status_code} khi {method} {path}: {response.text[:600]}")
        return response.json() if response.content else {}

    def find(self, resource, **match):
        rows = self.call("GET", f"/api/v1/{resource}/", params={"q": "(page_size:100)"})["result"]
        return next((row for row in rows if all(row.get(k) == v for k, v in match.items())), None)


def ensure_database(api):
    password = os.environ.get("SUPERSET_RO_PASSWORD")
    if not password:
        raise SystemExit("Thiếu SUPERSET_RO_PASSWORD trong .env")
    uri = f"postgresql+psycopg2://superset_ro:{quote_plus(password)}@db:5432/{os.getenv('DB_NAME', 'smartcrm')}"
    api.call("POST", "/api/v1/database/test_connection/", json={"sqlalchemy_uri": uri, "database_name": DATABASE_NAME})
    payload = {
        "database_name": DATABASE_NAME, "sqlalchemy_uri": uri, "expose_in_sqllab": True,
        "allow_dml": False, "allow_file_upload": False, "allow_run_async": False,
        "extra": json.dumps({"schemas_allowed_for_file_upload": [], "metadata_cache_timeout": {}}),
    }
    existing = api.find("database", database_name=DATABASE_NAME)
    if existing:
        api.call("PUT", f"/api/v1/database/{existing['id']}", json=payload)
        print(f"  ✓ Kết nối CSDL đã có (id={existing['id']}) – cập nhật URI")
        return existing["id"]
    database_id = api.call("POST", "/api/v1/database/", json=payload)["id"]
    print(f"  ✓ Tạo kết nối CSDL '{DATABASE_NAME}' (id={database_id})")
    return database_id


def ensure_dataset(api, database_id, table, main_dttm, labels, metrics):
    existing = api.find("dataset", table_name=table, schema=SCHEMA)
    dataset_id = existing["id"] if existing else api.call("POST", "/api/v1/dataset/", json={
        "database": database_id, "schema": SCHEMA, "table_name": table,
    })["id"]
    # Nạp lại danh sách cột từ view (view có thể vừa thêm cột khi chạy lại file SQL 01)
    api.call("PUT", f"/api/v1/dataset/{dataset_id}/refresh")
    detail = api.call("GET", f"/api/v1/dataset/{dataset_id}")["result"]
    columns = [{
        "id": col["id"], "column_name": col["column_name"],
        "verbose_name": labels.get(col["column_name"], col.get("verbose_name")),
        "is_dttm": col["column_name"] == main_dttm or col.get("is_dttm", False),
        "filterable": True, "groupby": True,
    } for col in detail["columns"]]
    existing_metrics = {m["metric_name"]: m["id"] for m in detail["metrics"]}
    metric_rows = [
        {"id": m["id"], "metric_name": m["metric_name"], "expression": m["expression"]}
        for m in detail["metrics"] if m["metric_name"] not in {name for name, *_ in metrics}
    ] + [
        {**({"id": existing_metrics[name]} if name in existing_metrics else {}),
         "metric_name": name, "verbose_name": label, "expression": expression, "d3format": fmt}
        for name, label, expression, fmt in metrics
    ]
    api.call("PUT", f"/api/v1/dataset/{dataset_id}", json={
        "main_dttm_col": main_dttm, "columns": columns, "metrics": metric_rows,
        "description": f"View chỉ đọc {SCHEMA}.{table} – sinh bởi sql/superset/01_analytics_views.sql",
    })
    print(f"  ✓ Dataset {SCHEMA}.{table} (id={dataset_id}) – {len(metrics)} metric")
    return dataset_id


def remove_dashboard(api, dashboard):
    charts = api.call("GET", f"/api/v1/dashboard/{dashboard['id']}/charts")["result"]
    api.call("DELETE", f"/api/v1/dashboard/{dashboard['id']}")
    for chart in charts:
        api.call("DELETE", f"/api/v1/chart/{chart['id']}")
    print(f"  ✓ Đã xoá dashboard cũ và {len(charts)} biểu đồ")


def build_position(chart_ids, names):
    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": DASHBOARD_TITLE}},
    }
    rows = [[("MARKDOWN-intro", 12, 22)]] + LAYOUT
    for index, row in enumerate(rows):
        row_id = f"ROW-{index}"
        position["GRID_ID"]["children"].append(row_id)
        position[row_id] = {"type": "ROW", "id": row_id, "children": [], "parents": ["ROOT_ID", "GRID_ID"],
                            "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        for key, width, height in row:
            parents = ["ROOT_ID", "GRID_ID", row_id]
            if key.startswith("MARKDOWN"):
                position[key] = {"type": "MARKDOWN", "id": key, "children": [], "parents": parents,
                                 "meta": {"width": width, "height": height, "code": MARKDOWN[key]}}
                position[row_id]["children"].append(key)
                continue
            element = f"CHART-{key}"
            position[row_id]["children"].append(element)
            position[element] = {"type": "CHART", "id": element, "children": [], "parents": parents,
                                 "meta": {"chartId": chart_ids[key], "width": width, "height": height,
                                          "sliceName": names[key]}}
    return position


def build_filters(chart_ids, dataset_ids, filtered_keys):
    in_scope = [chart_ids[k] for k in filtered_keys]
    excluded = [chart_id for key, chart_id in chart_ids.items() if key not in filtered_keys]
    common = {"cascadeParentIds": [], "type": "NATIVE_FILTER", "description": "", "tabsInScope": [],
              "chartsInScope": in_scope, "scope": {"rootPath": ["ROOT_ID"], "excluded": excluded},
              "defaultDataMask": {"extraFormData": {}, "filterState": {}, "ownState": {}}}
    select = {"enableEmptyFilter": False, "defaultToFirstItem": False, "multiSelect": True,
              "searchAllOptions": False, "inverseSelection": False}
    return [
        {**common, "id": "NATIVE_FILTER-thoi-gian", "name": "Khoảng thời gian", "filterType": "filter_time",
         "targets": [{}], "controlValues": {"enableEmptyFilter": False}},
        {**common, "id": "NATIVE_FILTER-nguon-khach", "name": "Nguồn khách", "filterType": "filter_select",
         "targets": [{"datasetId": dataset_ids["v_order_lines"], "column": {"name": "customer_source"}}],
         "controlValues": select},
        {**common, "id": "NATIVE_FILTER-nhom-khach", "name": "Nhóm khách", "filterType": "filter_select",
         "targets": [{"datasetId": dataset_ids["v_order_lines"], "column": {"name": "customer_type"}}],
         "controlValues": select},
        {**common, "id": "NATIVE_FILTER-nhom-sp", "name": "Nhóm sản phẩm", "filterType": "filter_select",
         "targets": [{"datasetId": dataset_ids["v_order_lines"], "column": {"name": "product_group"}}],
         "controlValues": select},
    ]


def ensure_embedding(api, dashboard_id):
    """Bật nhúng cho dashboard; Superset giữ nguyên UUID nếu đã bật từ trước."""
    result = api.call("POST", f"/api/v1/dashboard/{dashboard_id}/embedded",
                      json={"allowed_domains": EMBED_ORIGINS})["result"]
    print(f"  ✓ Cho phép nhúng vào: {', '.join(EMBED_ORIGINS)} (uuid={result['uuid']})")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="Xoá dashboard + biểu đồ cũ rồi dựng lại.")
    args = parser.parse_args()

    user = os.getenv("SUPERSET_ADMIN_USER", "admin")
    password = os.environ.get("SUPERSET_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("Thiếu SUPERSET_ADMIN_PASSWORD trong .env")
    print(f"Superset: {SUPERSET_URL} (đăng nhập '{user}')")
    api = Superset(SUPERSET_URL, user, password)

    existing = api.find("dashboard", slug=DASHBOARD_SLUG)
    if existing and not args.force:
        print(f"Dashboard đã tồn tại: {SUPERSET_URL}/superset/dashboard/{DASHBOARD_SLUG}/ (thêm --force để dựng lại)")
        ensure_embedding(api, existing["id"])
        return

    print("03 · Kết nối CSDL")
    database_id = ensure_database(api)

    print("04 · Dataset & biểu đồ")
    dataset_ids = {
        table: ensure_dataset(api, database_id, table, main_dttm, labels, metrics)
        for table, (main_dttm, labels, metrics) in DATASETS.items()
    }
    if existing:
        remove_dashboard(api, existing)
    dashboard_id = api.call("POST", "/api/v1/dashboard/", json={
        "dashboard_title": DASHBOARD_TITLE, "slug": DASHBOARD_SLUG, "published": True,
    })["id"]

    chart_ids, names, filtered = {}, {}, []
    for key, name, table, params, use_filters in CHARTS:
        form_data = {"datasource": f"{dataset_ids[table]}__table", "adhoc_filters": [],
                     "time_range": "No filter", **params}
        chart_ids[key] = api.call("POST", "/api/v1/chart/", json={
            "slice_name": name, "viz_type": params["viz_type"], "datasource_id": dataset_ids[table],
            "datasource_type": "table", "params": json.dumps(form_data), "dashboards": [dashboard_id],
        })["id"]
        names[key] = name
        if use_filters:
            filtered.append(key)
        print(f"  ✓ Biểu đồ: {name} ({params['viz_type']})")

    print("05 · Dashboard")
    api.call("PUT", f"/api/v1/dashboard/{dashboard_id}", json={
        "position_json": json.dumps(build_position(chart_ids, names)),
        "json_metadata": json.dumps({
            "color_scheme": "supersetColors", "refresh_frequency": 0, "cross_filters_enabled": True,
            "native_filter_configuration": build_filters(chart_ids, dataset_ids, filtered),
            "timed_refresh_immune_slices": [], "expanded_slices": {}, "label_colors": {},
            "shared_label_colors": {}, "color_scheme_domain": [], "default_filters": "{}",
        }),
    })
    print(f"  ✓ Dashboard: {SUPERSET_URL}/superset/dashboard/{DASHBOARD_SLUG}/")
    ensure_embedding(api, dashboard_id)


if __name__ == "__main__":
    sys.exit(main())
