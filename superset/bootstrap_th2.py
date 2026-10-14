"""TH2 – tạo kết nối "SmartCRM TH2 (chỉ đọc)" và 4 dataset kết quả AI (schema ai) trên Apache Superset qua REST API.

    python superset/bootstrap_th2.py

Chạy trên máy (ngoài Docker) bằng venv của dự án, sau khi đã chạy sql/superset/01, 02, 03 trên CSDL smartcrm_th2.
Không đụng vào kết nối, dataset, dashboard của TH1. Chạy lại nhiều lần không sao (cập nhật nhãn cột, metric).
Đọc .env: SUPERSET_PORT, SUPERSET_ADMIN_USER/PASSWORD, SUPERSET_RO_PASSWORD, TH2_DB_NAME (mặc định smartcrm_th2).
"""

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap_dashboard import SUPERSET_URL, Superset  # noqa: E402  (dùng lại lớp gọi API của TH1)

DATABASE_NAME = "SmartCRM TH2 (chỉ đọc)"
SCHEMA = "ai"
PCT = ".1%"
VND = ",d"

# Dataset: view -> (cột thời gian chính, {cột: nhãn tiếng Việt}, [(metric, nhãn, biểu thức SQL, định dạng)])
DATASETS = {
    "model_run": ("finished_at", {
        "batch": "Lần chạy", "module": "Module", "module_label": "Bài toán", "method": "Mã phương pháp",
        "method_label": "Phương pháp", "is_selected": "Được chọn", "finished_at": "Thời điểm chạy",
        "mae": "MAE (VNĐ)", "rmse": "RMSE (VNĐ)", "mape": "MAPE (%)", "auc": "AUC", "precision": "Precision",
        "recall": "Recall", "f1": "F1", "accuracy": "Accuracy", "macro_f1": "Macro F1", "n_train": "Số mẫu huấn luyện",
        "n_test": "Số mẫu kiểm tra", "avg_latency_ms": "Thời gian TB (ms)", "is_demo": "Dữ liệu giả",
    }, []),
    "revenue_forecast": ("month", {
        "month": "Tháng", "kind": "Mã loại", "kind_label": "Loại", "method": "Mã phương pháp",
        "method_label": "Phương pháp", "is_selected": "Được chọn", "actual": "Doanh thu thực tế",
        "forecast": "Dự báo", "lower": "Cận dưới 95%", "upper": "Cận trên 95%", "batch": "Lần chạy",
    }, [
        ("doanh_thu_thuc_te", "Doanh thu thực tế (VNĐ)", "SUM(actual)", VND),
        ("doanh_thu_du_bao", "Doanh thu dự báo (VNĐ)", "SUM(forecast)", VND),
        ("can_duoi", "Cận dưới 95% (VNĐ)", "SUM(lower)", VND),
        ("can_tren", "Cận trên 95% (VNĐ)", "SUM(upper)", VND),
    ]),
    "churn_score": ("last_order_date", {
        "customer_id": "Mã khách", "customer_name": "Khách hàng", "customer_type": "Nhóm khách",
        "customer_source": "Nguồn khách", "staff_name": "Nhân viên phụ trách", "last_order_date": "Đơn gần nhất",
        "total_spent": "Tổng chi tiêu", "method": "Mã phương pháp", "method_label": "Phương pháp",
        "is_selected": "Được chọn", "probability": "Xác suất rời bỏ", "risk_band": "Mã mức rủi ro",
        "risk_label": "Mức rủi ro", "batch": "Lần chạy",
    }, [
        ("so_khach", "Số khách", "COUNT(*)", ",d"),
        ("rui_ro_tb", "Xác suất rời bỏ trung bình", "AVG(probability)", PCT),
        ("chi_tieu_rui_ro", "Tổng chi tiêu của khách (VNĐ)", "SUM(total_spent)", VND),
    ]),
    "interaction_sentiment": ("interaction_date", {
        "interaction_id": "Mã tương tác", "interaction_date": "Thời gian", "channel": "Kênh",
        "customer_name": "Khách hàng", "method": "Mã phương pháp", "method_label": "Phương pháp",
        "is_selected": "Được chọn", "label_pred": "Cảm xúc (dự đoán)", "label_true": "Cảm xúc (nhãn đúng)",
        "is_correct": "Dự đoán đúng", "confidence": "Độ tin cậy", "latency_ms": "Thời gian (ms)", "batch": "Lần chạy",
    }, [
        ("so_cau", "Số tin nhắn", "COUNT(*)", ",d"),
        ("ti_le_dung", "Tỉ lệ dự đoán đúng", "AVG(CASE WHEN is_correct THEN 1.0 ELSE 0 END)", PCT),
        ("ti_le_tieu_cuc", "Tỉ lệ tiêu cực", "AVG(CASE WHEN label_pred = 'Tiêu cực' THEN 1.0 ELSE 0 END)", PCT),
    ]),
}


def ensure_database(api):
    password = os.environ.get("SUPERSET_RO_PASSWORD")
    if not password:
        raise SystemExit("Thiếu SUPERSET_RO_PASSWORD trong .env")
    db_name = os.getenv("TH2_DB_NAME", "smartcrm_th2")
    uri = f"postgresql+psycopg2://superset_ro:{quote_plus(password)}@db:5432/{db_name}"
    api.call("POST", "/api/v1/database/test_connection/", json={"sqlalchemy_uri": uri, "database_name": DATABASE_NAME})
    payload = {
        "database_name": DATABASE_NAME, "sqlalchemy_uri": uri, "expose_in_sqllab": True,
        "allow_dml": False, "allow_file_upload": False, "allow_run_async": False,
    }
    existing = api.find("database", database_name=DATABASE_NAME)
    if existing:
        api.call("PUT", f"/api/v1/database/{existing['id']}", json=payload)
        print(f"  ✓ Kết nối '{DATABASE_NAME}' đã có (id={existing['id']}) – cập nhật")
        return existing["id"]
    database_id = api.call("POST", "/api/v1/database/", json=payload)["id"]
    print(f"  ✓ Tạo kết nối '{DATABASE_NAME}' (id={database_id}) tới {db_name}")
    return database_id


def find_dataset(api, database_id, table):
    rows = api.call("GET", "/api/v1/dataset/", params={"q": "(page_size:100)"})["result"]
    return next((row for row in rows if row["table_name"] == table and row["schema"] == SCHEMA
                 and row["database"]["id"] == database_id), None)


def ensure_dataset(api, database_id, table, main_dttm, labels, metrics):
    existing = find_dataset(api, database_id, table)
    dataset_id = existing["id"] if existing else api.call("POST", "/api/v1/dataset/", json={
        "database": database_id, "schema": SCHEMA, "table_name": table,
    })["id"]
    api.call("PUT", f"/api/v1/dataset/{dataset_id}/refresh")
    detail = api.call("GET", f"/api/v1/dataset/{dataset_id}")["result"]
    columns = [{
        "id": col["id"], "column_name": col["column_name"],
        "verbose_name": labels.get(col["column_name"], col.get("verbose_name")),
        "is_dttm": col["column_name"] == main_dttm or col.get("is_dttm", False),
        "filterable": True, "groupby": True,
    } for col in detail["columns"]]
    existing_metrics = {m["metric_name"]: m["id"] for m in detail["metrics"]}
    names = {name for name, *_ in metrics}
    metric_rows = [
        {"id": m["id"], "metric_name": m["metric_name"], "expression": m["expression"]}
        for m in detail["metrics"] if m["metric_name"] not in names
    ] + [
        {**({"id": existing_metrics[name]} if name in existing_metrics else {}),
         "metric_name": name, "verbose_name": label, "expression": expression, "d3format": fmt}
        for name, label, expression, fmt in metrics
    ]
    api.call("PUT", f"/api/v1/dataset/{dataset_id}", json={
        "main_dttm_col": main_dttm, "columns": columns, "metrics": metric_rows,
        "description": f"TH2 – view chỉ đọc {SCHEMA}.{table} (sql/superset/03_ai_views.sql)",
    })
    print(f"  ✓ Dataset {SCHEMA}.{table} (id={dataset_id})")
    return dataset_id


def main():
    user = os.getenv("SUPERSET_ADMIN_USER", "admin")
    password = os.environ.get("SUPERSET_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("Thiếu SUPERSET_ADMIN_PASSWORD trong .env")
    print(f"Superset: {SUPERSET_URL} (đăng nhập '{user}')")
    api = Superset(SUPERSET_URL, user, password)
    database_id = ensure_database(api)
    for table, (main_dttm, labels, metrics) in DATASETS.items():
        ensure_dataset(api, database_id, table, main_dttm, labels, metrics)


if __name__ == "__main__":
    sys.exit(main())
