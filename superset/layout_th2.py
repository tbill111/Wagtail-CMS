"""TH2 – ghép 16 biểu đồ AI Insights vào 4 tab của dashboard "SmartCRM – AI Insights" (checklist 04).

    python superset/layout_th2.py

Biểu đồ do agent tạo QUA SUPERSET MCP (tài khoản mcp_agent, chỉ tạo được biểu đồ, không sửa được dashboard của admin –
đúng thiết kế phân quyền). Script này dùng tài khoản admin để: gắn biểu đồ vào dashboard, sắp 4 tab
Tổng quan · Dự báo · Rời bỏ · Cảm xúc, thêm khối giới thiệu nguồn dữ liệu và bộ lọc. Biểu đồ được tìm theo TÊN (tiền tố
tab), nên chạy được trên máy khác sau khi tạo lại biểu đồ. Chạy lại nhiều lần không sao. Cần chạy bootstrap_th2.py trước.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap_dashboard import SUPERSET_URL, Superset  # noqa: E402
from bootstrap_th2 import DASHBOARD_SLUG, DASHBOARD_TITLE, DATABASE_NAME, find_dataset  # noqa: E402

# Tab -> các hàng; mỗi hàng là [(tên biểu đồ hoặc khoá MARKDOWN, độ rộng /12, chiều cao)]
TABS = {
    "Tổng quan": [
        [("MARKDOWN-gioi-thieu", 12, 26)],
        [("[Tổng quan] Độ chính xác các mô hình", 6, 60), ("[Tổng quan] Doanh thu thực tế và dự báo", 6, 60)],
        [("[Tổng quan] Số khách theo mức rủi ro rời bỏ", 6, 55), ("[Tổng quan] Tỉ lệ cảm xúc", 6, 55)],
    ],
    "Dự báo": [
        [("[Dự báo] Doanh thu dự báo tháng tới", 4, 50), ("[Dự báo] Doanh thu thực tế và dự báo 6 tháng", 8, 50)],
        [("[Dự báo] So sánh 3 phương pháp trên 6 tháng kiểm tra", 7, 55), ("[Dự báo] Sai số các phương pháp", 5, 55)],
    ],
    "Rời bỏ": [
        [("[Rời bỏ] Số khách theo mức rủi ro", 5, 55), ("[Rời bỏ] So sánh mô hình", 7, 55)],
        [("[Rời bỏ] 20 khách rủi ro cao nhất", 7, 70), ("[Rời bỏ] Rủi ro trung bình theo tháng mua gần nhất", 5, 70)],
    ],
    "Cảm xúc": [
        [("[Cảm xúc] Cảm xúc theo tháng", 7, 55), ("[Cảm xúc] Cảm xúc theo kênh", 5, 55)],
        [("[Cảm xúc] Độ chính xác: từ điển và Gemini", 5, 50), ("[Cảm xúc] Dự đoán đúng và sai", 7, 50)],
    ],
}
MARKDOWN = {
    "MARKDOWN-gioi-thieu": """### SmartCRM – AI Insights

Kết quả của **3 mô hình AI** chạy trên dữ liệu SmartCRM (CSDL `smartcrm_th2`), đọc qua các view chỉ đọc `ai.*`:

* **Dự báo doanh thu** 6 tháng tới – so sánh *Cùng kỳ năm trước*, *Holt-Winters*, *SARIMA* (chọn MAPE nhỏ nhất).
* **Khách sắp rời bỏ** – *Luật RFM*, *Logistic Regression*, *Random Forest* (chọn AUC lớn nhất).
* **Cảm xúc tin nhắn** – *Từ điển từ khoá* và *LLM Gemini* (chọn Macro F1 lớn nhất).

Số liệu lấy từ **lần chạy mô hình mới nhất** (`python manage.py run_ai_pipeline`). Dữ liệu bán hàng: Online Retail II
(UCI, dời +14 năm, 1 GBP = 33.000 ₫); nhận xét: bộ dữ liệu tiếng Việt có nhãn trên Hugging Face.""",
}
# Bộ lọc: (id, tên, dataset view, cột)
FILTERS = [
    ("NATIVE_FILTER-muc-rui-ro", "Mức rủi ro", "churn_score", "risk_label"),
    ("NATIVE_FILTER-nhom-khach", "Nhóm khách", "churn_score", "customer_type"),
    ("NATIVE_FILTER-kenh", "Kênh", "interaction_sentiment", "channel"),
]


def slug(text):
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


def find_charts(api):
    """{tên biểu đồ: id} cho mọi biểu đồ có tên trong TABS."""
    wanted = {name for rows in TABS.values() for row in rows for name, *_ in row if not name.startswith("MARKDOWN")}
    found = {}
    for prefix in ("Tổng quan", "Dự báo", "Rời bỏ", "Cảm xúc"):
        rows = api.call("GET", "/api/v1/chart/", params={
            "q": f"(filters:!((col:slice_name,opr:ct,value:'{prefix}')),page_size:100)"})["result"]
        for chart in sorted(rows, key=lambda c: c["id"]):  # trùng tên → lấy biểu đồ mới nhất
            if chart["slice_name"] in wanted:
                found[chart["slice_name"]] = chart["id"]
    missing = sorted(wanted - set(found))
    if missing:
        raise SystemExit("Chưa có biểu đồ (tạo qua MCP theo docs/th2/bao_cao/06_dashboard.md): " + "; ".join(missing))
    return found


def build_position(chart_ids):
    tab_ids = [f"TAB-{slug(tab)}" for tab in TABS]
    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["TABS-ai"]},
        "TABS-ai": {"type": "TABS", "id": "TABS-ai", "children": tab_ids, "parents": ["ROOT_ID"]},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": DASHBOARD_TITLE}},
    }
    for tab, tab_id in zip(TABS, tab_ids):
        position[tab_id] = {"type": "TAB", "id": tab_id, "children": [], "parents": ["ROOT_ID", "TABS-ai"],
                            "meta": {"text": tab, "defaultText": "Tab title"}}
        parents = ["ROOT_ID", "TABS-ai", tab_id]
        for index, row in enumerate(TABS[tab]):
            row_id = f"ROW-{tab_id[4:]}-{index}"
            position[tab_id]["children"].append(row_id)
            position[row_id] = {"type": "ROW", "id": row_id, "children": [], "parents": parents,
                                "meta": {"background": "BACKGROUND_TRANSPARENT"}}
            for name, width, height in row:
                if name.startswith("MARKDOWN"):
                    element = {"type": "MARKDOWN", "meta": {"width": width, "height": height, "code": MARKDOWN[name]}}
                    key = name
                else:
                    key = f"CHART-{chart_ids[name]}"
                    element = {"type": "CHART", "meta": {"chartId": chart_ids[name], "width": width,
                                                         "height": height, "sliceName": name}}
                position[row_id]["children"].append(key)
                position[key] = {**element, "id": key, "children": [], "parents": parents + [row_id]}
    return position


def build_filters(api):
    database_id = api.find("database", database_name=DATABASE_NAME)["id"]
    select = {"enableEmptyFilter": False, "defaultToFirstItem": False, "multiSelect": True,
              "searchAllOptions": False, "inverseSelection": False}
    filters = []
    for filter_id, name, table, column in FILTERS:
        dataset = find_dataset(api, database_id, table)
        filters.append({
            "id": filter_id, "name": name, "filterType": "filter_select", "type": "NATIVE_FILTER",
            "targets": [{"datasetId": dataset["id"], "column": {"name": column}}], "controlValues": select,
            "cascadeParentIds": [], "description": "", "chartsInScope": [], "tabsInScope": [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "defaultDataMask": {"extraFormData": {}, "filterState": {}, "ownState": {}},
        })
    return filters


def main():
    password = os.environ.get("SUPERSET_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("Thiếu SUPERSET_ADMIN_PASSWORD trong .env")
    api = Superset(SUPERSET_URL, os.getenv("SUPERSET_ADMIN_USER", "admin"), password)
    dashboard = api.find("dashboard", slug=DASHBOARD_SLUG)
    if not dashboard:
        raise SystemExit(f"Chưa có dashboard '{DASHBOARD_SLUG}' – chạy python superset/bootstrap_th2.py trước.")
    chart_ids = find_charts(api)
    for name, chart_id in chart_ids.items():  # gắn biểu đồ vào dashboard (giữ các dashboard khác nếu có)
        current = api.call("GET", f"/api/v1/chart/{chart_id}")["result"]
        ids = sorted({d["id"] for d in current.get("dashboards", [])} | {dashboard["id"]})
        api.call("PUT", f"/api/v1/chart/{chart_id}", json={"dashboards": ids})
    metadata = json.loads(api.call("GET", f"/api/v1/dashboard/{dashboard['id']}")["result"].get("json_metadata")
                          or "{}")
    metadata.update({"color_scheme": "supersetColors", "cross_filters_enabled": True,
                     "native_filter_configuration": build_filters(api)})
    api.call("PUT", f"/api/v1/dashboard/{dashboard['id']}", json={
        "position_json": json.dumps(build_position(chart_ids), ensure_ascii=False),
        "json_metadata": json.dumps(metadata, ensure_ascii=False),
    })
    print(f"  ✓ Dashboard '{DASHBOARD_TITLE}' (id={dashboard['id']}): {len(TABS)} tab, {len(chart_ids)} biểu đồ, "
          f"{len(FILTERS)} bộ lọc")
    print(f"  ✓ {SUPERSET_URL}/superset/dashboard/{DASHBOARD_SLUG}/")


if __name__ == "__main__":
    sys.exit(main())
