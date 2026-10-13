"""Cấu hình Apache Superset cho TH1 SmartCRM. Mọi bí mật đọc từ biến môi trường."""

import os
from urllib.parse import quote_plus

# Bắt buộc: khoá ký phiên đăng nhập. Superset từ chối chạy nếu dùng khoá mặc định.
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# Metadata của Superset (chart, dashboard, user) lưu trong CSDL riêng, không dùng chung với Wagtail
SQLALCHEMY_DATABASE_URI = (
    "postgresql+psycopg2://superset_meta:"
    f"{quote_plus(os.environ['SUPERSET_META_PASSWORD'])}@db:5432/superset_meta"
)

# Chặn kết nối không an toàn (SQLite, file cục bộ) – chỉ cho phép CSDL qua mạng
PREVENT_UNSAFE_DB_CONNECTIONS = True

# Giới hạn số dòng trả về để tránh truy vấn quá nặng
ROW_LIMIT = 10000
SQL_MAX_ROW = 10000

FEATURE_FLAGS = {
    "DASHBOARD_CROSS_FILTERS": True,
}

# ----- Nhúng dashboard vào SmartCRM (Embedded SDK + guest token) -----
FEATURE_FLAGS["EMBEDDED_SUPERSET"] = True

# Khoá ký guest token, tách riêng với SECRET_KEY
GUEST_TOKEN_JWT_SECRET = os.environ["SUPERSET_GUEST_TOKEN_SECRET"]
GUEST_TOKEN_JWT_EXP_SECONDS = 300
# Người xem qua guest token nhận quyền giao diện của Gamma; dữ liệu chỉ giới hạn trong dashboard được cấp
GUEST_ROLE_NAME = "Gamma"

# Chỉ các địa chỉ SmartCRM này được đặt Superset trong iframe (CSP frame-ancestors)
EMBED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("SUPERSET_EMBED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
    if origin.strip()
]

# Giữ nguyên CSP mặc định của Superset 4.1, chỉ thêm frame-ancestors
TALISMAN_ENABLED = True
TALISMAN_CONFIG = {
    "content_security_policy": {
        "base-uri": ["'self'"],
        "default-src": ["'self'"],
        "img-src": ["'self'", "blob:", "data:", "https://apachesuperset.gateway.scarf.sh", "https://static.scarf.sh/"],
        "worker-src": ["'self'", "blob:"],
        "connect-src": ["'self'", "https://api.mapbox.com", "https://events.mapbox.com"],
        "object-src": "'none'",
        "style-src": ["'self'", "'unsafe-inline'"],
        "script-src": ["'self'", "'strict-dynamic'"],
        "frame-ancestors": ["'self'", *EMBED_ORIGINS],
    },
    "content_security_policy_nonce_in": ["script-src"],
    "force_https": False,
    "session_cookie_secure": False,
    # Trình duyệt ưu tiên frame-ancestors; bỏ X-Frame-Options: SAMEORIGIN để không chặn iframe
    "frame_options": None,
}
