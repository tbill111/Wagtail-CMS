# TH2 – Cài Superset MCP cho Claude

MCP (Model Context Protocol) cho phép Claude **gọi trực tiếp Superset**: xem dataset, chạy truy vấn đọc, tạo biểu đồ và
dashboard theo câu lệnh tiếng Việt. Nhóm dùng **`aptro/superset-mcp`** (MIT, gọi REST API của Superset, tác giả đã thử
với Superset 4.1.1; nhóm đã kiểm chứng chạy được với 4.1.2).

> Làm **sau** khi đã xong `docs/th2/CAI_DAT.md` (có kết nối "SmartCRM TH2 (chỉ đọc)" và 4 dataset `ai.*`).

## 1. Tải và cài MCP server (ngoài repo)

Đặt ở thư mục `tools/` **cạnh** thư mục `smartcrm` (không để trong repo):

```powershell
cd ..                                   # ra thư mục chứa smartcrm
mkdir tools
git clone --depth 1 https://github.com/aptro/superset-mcp.git tools/superset-mcp
cd tools/superset-mcp
pip install uv                          # nếu chưa có uv
uv sync                                 # tạo .venv và cài thư viện
```
**Đúng khi:** có file `tools/superset-mcp/.venv/Scripts/python.exe`.

## 2. Tài khoản Superset riêng cho MCP

MCP **không dùng tài khoản admin**. Nhóm trưởng tạo tài khoản `mcp_agent` với đúng 3 vai trò:

| Vai trò | Cho phép |
|---|---|
| `Gamma` | Xem, tạo, sửa biểu đồ và dashboard (không tạo được kết nối CSDL, không quản lý người dùng) |
| `sql_lab` | Chạy truy vấn trong SQL Lab |
| `TH2_MCP` (tự tạo) | Chỉ `database_access` trên kết nối **"SmartCRM TH2 (chỉ đọc)"** |

Trên máy mình, mở Superset bằng admin → **Settings → List Users → +** tạo `mcp_agent`, chọn 3 vai trò trên
(vai trò `TH2_MCP`: **Settings → List Roles → +**, thêm quyền `database access on [SmartCRM TH2 (chỉ đọc)]`).

Tạo file `tools/superset-mcp/.env` (file này **không** nằm trong repo):

```
SUPERSET_BASE_URL=http://localhost:8088
SUPERSET_USERNAME=mcp_agent
SUPERSET_PASSWORD=<mật khẩu của mcp_agent>
```
Đổi `8088` theo `SUPERSET_PORT` trong `.env` của dự án.

## 3. Nối MCP với Claude

### Claude Code (VS Code / terminal)
Tạo file `.mcp.json` ở **thư mục bạn mở Claude Code** (thư mục cha của `smartcrm`), thay đường dẫn cho đúng máy mình:

```json
{
  "mcpServers": {
    "superset": {
      "command": "D:/duong-dan/tools/superset-mcp/.venv/Scripts/python.exe",
      "args": ["D:/duong-dan/tools/superset-mcp/main.py"]
    }
  }
}
```
Khởi động lại Claude Code, chấp nhận server `superset` khi được hỏi. Gõ `/mcp` để xem trạng thái.

### Claude Desktop
**Settings → Developer → Edit Config**, thêm khối `"superset"` như trên vào `mcpServers` của `claude_desktop_config.json`,
rồi khởi động lại Claude Desktop.

## 4. Kiểm tra

Hỏi Claude lần lượt:
1. *"Đăng nhập Superset rồi liệt kê các database và dataset bạn thấy."*
   → **Đúng khi:** chỉ thấy "SmartCRM TH2 (chỉ đọc)" và 4 dataset `ai.model_run`, `ai.revenue_forecast`, `ai.churn_score`,
   `ai.interaction_sentiment`.
2. *"Chạy truy vấn: SELECT module, method, is_selected FROM ai.model_run"* → có kết quả.
3. *"Chạy truy vấn: DELETE FROM ai.model_run"* → **phải bị từ chối** (DML_NOT_ALLOWED_ERROR).

## Lỗi hay gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `401 Not authorized` khi đăng nhập | Sai mật khẩu trong `tools/superset-mcp/.env`, hoặc sai cổng `SUPERSET_BASE_URL` |
| Thấy được database nhưng không thấy dataset | Vai trò `TH2_MCP` chưa có quyền `database access` đúng kết nối |
| Claude không thấy công cụ `superset_*` | Kiểm tra đường dẫn trong `.mcp.json`, khởi động lại Claude, gõ `/mcp` |
| `superset_user_get_current` báo 401 | Bình thường – vai trò Gamma không có quyền xem hồ sơ, không ảnh hưởng các công cụ khác |
