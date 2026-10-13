#!/bin/sh
# Chạy tự động MỘT lần khi volume PostgreSQL còn trống (docker-entrypoint-initdb.d).
# Tạo CSDL + tài khoản riêng để Superset lưu metadata (chart, dashboard, người dùng),
# tách biệt hoàn toàn với CSDL nghiệp vụ của Wagtail.
set -e
psql -v ON_ERROR_STOP=1 -v meta_password="$SUPERSET_META_PASSWORD" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE superset_meta LOGIN PASSWORD :'meta_password';
CREATE DATABASE superset_meta OWNER superset_meta;
REVOKE ALL ON DATABASE superset_meta FROM PUBLIC;
SQL
