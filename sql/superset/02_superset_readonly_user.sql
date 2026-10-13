-- =====================================================================================
-- TH1 · 02 – Tài khoản CHỈ ĐỌC để Apache Superset kết nối CSDL Wagtail CRM
-- =====================================================================================
-- Nguyên tắc quyền tối thiểu (least privilege):
--   * superset_ro chỉ được SELECT các view trong schema `analytics`
--   * KHÔNG đọc được bảng gốc (crm_customer có email/SĐT, auth_user có mật khẩu băm…)
--   * Phiên luôn ở chế độ read-only, giới hạn thời gian truy vấn và số kết nối
--
-- Chạy SAU file 01 (mật khẩu truyền qua biến, không ghi cứng trong file):
--   docker compose exec db sh -c 'psql -U smartcrm -d smartcrm -v ON_ERROR_STOP=1 \
--       -v ro_password="$SUPERSET_RO_PASSWORD" -f /sql/02_superset_readonly_user.sql'
-- Chạy lại nhiều lần không sao (đổi mật khẩu = sửa .env rồi chạy lại).
-- =====================================================================================

BEGIN;

SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'superset_ro') AS need_create \gset
\if :need_create
    CREATE ROLE superset_ro LOGIN;
\endif

ALTER ROLE superset_ro WITH LOGIN PASSWORD :'ro_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 10;
ALTER ROLE superset_ro SET default_transaction_read_only = on;
ALTER ROLE superset_ro SET statement_timeout = '30s';

-- Chỉ cho kết nối vào CSDL này; không ai khác (PUBLIC) tự động có quyền kết nối
REVOKE ALL ON DATABASE :"DBNAME" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"DBNAME" TO superset_ro;

-- Bảng gốc nằm ở schema public: thu hồi quyền mặc định của PUBLIC để superset_ro không thấy
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM superset_ro;

-- Chỉ mở schema analytics
GRANT USAGE ON SCHEMA analytics TO superset_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO superset_ro;
-- View tạo lại sau này (chạy lại file 01) tự động được cấp quyền đọc
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO superset_ro;

COMMIT;

-- =====================================================================================
-- VERIFY – mọi dòng phải có ket_qua = 'OK'
-- =====================================================================================
SELECT 'Không đọc được bảng gốc crm_customer' AS kiem_tra,
       CASE WHEN NOT has_table_privilege('superset_ro', 'public.crm_customer', 'SELECT') THEN 'OK' ELSE 'LỖI' END AS ket_qua
UNION ALL
SELECT 'Không đọc được bảng auth_user',
       CASE WHEN NOT has_table_privilege('superset_ro', 'public.auth_user', 'SELECT') THEN 'OK' ELSE 'LỖI' END
UNION ALL
SELECT 'Không dùng được schema public',
       CASE WHEN NOT has_schema_privilege('superset_ro', 'public', 'USAGE') THEN 'OK' ELSE 'LỖI' END
UNION ALL
SELECT 'Đọc được analytics.' || c.relname,
       CASE WHEN has_table_privilege('superset_ro', c.oid, 'SELECT') THEN 'OK' ELSE 'LỖI' END
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'analytics' AND c.relkind = 'v'
UNION ALL
SELECT 'Không có quyền ghi (INSERT) vào view',
       CASE WHEN NOT has_table_privilege('superset_ro', 'analytics.v_orders', 'INSERT') THEN 'OK' ELSE 'LỖI' END
UNION ALL
SELECT 'Phiên mặc định read-only',
       CASE WHEN EXISTS (SELECT 1 FROM pg_db_role_setting s JOIN pg_roles r ON r.oid = s.setrole
                         WHERE r.rolname = 'superset_ro'
                           AND 'default_transaction_read_only=on' = ANY (s.setconfig)) THEN 'OK' ELSE 'LỖI' END;
