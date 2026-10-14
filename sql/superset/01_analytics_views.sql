-- =====================================================================================
-- TH1 · 01 – Tầng dữ liệu phân tích cho Apache Superset (PostgreSQL)
-- =====================================================================================
-- Tạo schema `analytics` gồm các VIEW chỉ đọc, gom sẵn dữ liệu nghiệp vụ của Wagtail CRM:
--   v_order_lines   mỗi dòng = 1 sản phẩm trong 1 đơn (dataset chính cho doanh thu)
--   v_orders        mỗi dòng = 1 đơn hàng
--   v_customers     mỗi dòng = 1 khách hàng + chỉ số mua hàng (KHÔNG có email, SĐT)
--   v_products      mỗi dòng = 1 sản phẩm + tồn kho + số lượng đã bán
--   v_interactions  mỗi dòng = 1 lượt tương tác (KHÔNG có nội dung tin nhắn)
--   v_customer_rfm  mỗi dòng = 1 khách ĐÃ MUA + điểm RFM (Recency/Frequency/Monetary) + phân khúc
--   v_cohort        mỗi dòng = (tháng mua đầu tiên, số tháng sau đó) + số khách quay lại mua
--
-- Quy ước khớp với trang Tổng quan /crm/ (crm/analytics.py):
--   * Doanh thu = SUM(số lượng × đơn giá) của đơn ở trạng thái Hoàn thành (completed)
--   * Thời gian quy đổi về giờ Việt Nam (Asia/Ho_Chi_Minh) trước khi nhóm theo ngày/tháng
--
-- Chạy (sau `python manage.py migrate`), chạy lại nhiều lần không sao:
--   docker compose exec db psql -U smartcrm -d smartcrm -v ON_ERROR_STOP=1 -f /sql/01_analytics_views.sql
-- Lưu ý: nếu migration sau này đổi/xoá cột mà view đang dùng, PostgreSQL sẽ chặn –
--        khi đó DROP SCHEMA analytics CASCADE, chạy migrate rồi chạy lại file này và file 02.
-- =====================================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS analytics;
COMMENT ON SCHEMA analytics IS 'View chỉ đọc cho Apache Superset (TH1) – không chứa dữ liệu cá nhân nhạy cảm';

DROP VIEW IF EXISTS analytics.v_cohort, analytics.v_customer_rfm,
                    analytics.v_order_lines, analytics.v_orders, analytics.v_customers,
                    analytics.v_products, analytics.v_interactions;

-- ------------------------------------------------------------------ nhãn tiếng Việt dùng chung
CREATE OR REPLACE FUNCTION analytics.staff_name(u auth_user) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(NULLIF(TRIM(u.last_name || ' ' || u.first_name), ''), u.username, 'Chưa phân công')
$$;

-- ------------------------------------------------------------------ v_order_lines
CREATE VIEW analytics.v_order_lines AS
SELECT
    i.id                                                   AS line_id,
    o.id                                                   AS order_id,
    o.code                                                 AS order_code,
    (o.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')         AS order_date,
    o.status                                               AS order_status,
    CASE o.status WHEN 'new' THEN 'Mới' WHEN 'processing' THEN 'Đang xử lý'
                  WHEN 'completed' THEN 'Hoàn thành' WHEN 'cancelled' THEN 'Huỷ' END AS order_status_label,
    (o.status = 'completed')                               AS is_completed,
    c.id                                                   AS customer_id,
    c.name                                                 AS customer_name,
    CASE WHEN TRIM(c.company) <> '' THEN 'Doanh nghiệp' ELSE 'Cá nhân / cửa hàng' END AS customer_type,
    CASE c.source WHEN 'website' THEN 'Website' WHEN 'facebook' THEN 'Facebook'
                  WHEN 'referral' THEN 'Giới thiệu' ELSE 'Khác' END            AS customer_source,
    COALESCE(analytics.staff_name(u), 'Chưa phân công')    AS staff_name,
    p.sku                                                  AS product_sku,
    COALESCE(p.name, i.product_name)                       AS product_name,
    CASE WHEN p.id IS NULL THEN 'Khác'
         WHEN p.track_stock THEN 'Thiết bị & vật tư'
         WHEN p.sku LIKE 'DV-%' THEN 'Dịch vụ'
         ELSE 'Phần mềm' END                               AS product_group,
    i.quantity,
    i.unit_price,
    (i.quantity * i.unit_price)                            AS line_total
FROM crm_orderitem i
JOIN crm_order o     ON o.id = i.order_id
JOIN crm_customer c  ON c.id = o.customer_id
LEFT JOIN crm_product p ON p.id = i.product_id
LEFT JOIN auth_user u   ON u.id = c.assigned_staff_id;

COMMENT ON VIEW analytics.v_order_lines IS 'Dòng sản phẩm trong đơn – doanh thu = SUM(line_total) WHERE is_completed';

-- ------------------------------------------------------------------ v_orders
CREATE VIEW analytics.v_orders AS
SELECT
    order_id, order_code, order_date, order_status, order_status_label, is_completed,
    customer_id, customer_name, customer_type, customer_source, staff_name,
    COUNT(*)            AS line_count,
    SUM(quantity)       AS total_quantity,
    SUM(line_total)     AS total_amount
FROM analytics.v_order_lines
GROUP BY order_id, order_code, order_date, order_status, order_status_label, is_completed,
         customer_id, customer_name, customer_type, customer_source, staff_name;

-- ------------------------------------------------------------------ v_customers
CREATE VIEW analytics.v_customers AS
WITH order_stats AS (
    SELECT customer_id,
           COUNT(*)                                        AS orders_count,
           COUNT(*) FILTER (WHERE is_completed)            AS completed_orders,
           COALESCE(SUM(total_amount) FILTER (WHERE is_completed), 0) AS total_spent,
           MIN(order_date)                                 AS first_order_date,
           MAX(order_date)                                 AS last_order_date
    FROM analytics.v_orders
    GROUP BY customer_id
), interaction_stats AS (
    SELECT customer_id, COUNT(*) AS interactions_count
    FROM crm_interactionlog
    GROUP BY customer_id
)
SELECT
    c.id                                                   AS customer_id,
    c.name                                                 AS customer_name,
    NULLIF(TRIM(c.company), '')                            AS company,
    CASE WHEN TRIM(c.company) <> '' THEN 'Doanh nghiệp' ELSE 'Cá nhân / cửa hàng' END AS customer_type,
    c.status                                               AS customer_status,
    CASE c.status WHEN 'lead' THEN '1. Tiềm năng' WHEN 'caring' THEN '2. Đang chăm sóc'
                  WHEN 'customer' THEN '3. Đã mua hàng' WHEN 'churned' THEN '4. Đã rời bỏ' END AS customer_status_label,
    CASE c.source WHEN 'website' THEN 'Website' WHEN 'facebook' THEN 'Facebook'
                  WHEN 'referral' THEN 'Giới thiệu' ELSE 'Khác' END            AS customer_source,
    CASE c.ai_priority WHEN 'high' THEN 'Cao' WHEN 'medium' THEN 'Trung bình'
                       WHEN 'low' THEN 'Thấp' ELSE 'Chưa phân tích' END        AS ai_priority,
    CASE c.ai_sentiment WHEN 'positive' THEN 'Tích cực' WHEN 'neutral' THEN 'Trung lập'
                        WHEN 'negative' THEN 'Tiêu cực' ELSE 'Chưa phân tích' END AS ai_sentiment,
    COALESCE(analytics.staff_name(u), 'Chưa phân công')    AS staff_name,
    (c.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')         AS created_date,
    COALESCE(os.orders_count, 0)                           AS orders_count,
    COALESCE(os.completed_orders, 0)                       AS completed_orders,
    COALESCE(os.total_spent, 0)                            AS total_spent,
    os.first_order_date,
    os.last_order_date,
    (CURRENT_DATE - os.last_order_date::date)              AS days_since_last_order,
    COALESCE(ist.interactions_count, 0)                    AS interactions_count
FROM crm_customer c
LEFT JOIN order_stats os        ON os.customer_id = c.id
LEFT JOIN interaction_stats ist ON ist.customer_id = c.id
LEFT JOIN auth_user u           ON u.id = c.assigned_staff_id;

COMMENT ON VIEW analytics.v_customers IS 'Khách hàng + chỉ số mua hàng; cố ý bỏ email/số điện thoại';

-- ------------------------------------------------------------------ v_products
CREATE VIEW analytics.v_products AS
SELECT
    p.id                                                   AS product_id,
    p.sku                                                  AS product_sku,
    p.name                                                 AS product_name,
    CASE WHEN p.track_stock THEN 'Thiết bị & vật tư'
         WHEN p.sku LIKE 'DV-%' THEN 'Dịch vụ' ELSE 'Phần mềm' END AS product_group,
    p.unit,
    p.price,
    p.track_stock,
    p.is_active,
    CASE WHEN p.track_stock THEN p.stock END               AS stock,
    CASE WHEN p.track_stock THEN p.min_stock END           AS min_stock,
    (p.is_active AND p.track_stock AND p.stock <= p.min_stock) AS is_low_stock,
    CASE WHEN p.is_active AND p.track_stock AND p.stock <= p.min_stock THEN 'Có' ELSE 'Không' END AS low_stock_label,
    COALESCE(SUM(l.quantity) FILTER (WHERE l.is_completed), 0)   AS sold_quantity,
    COALESCE(SUM(l.line_total) FILTER (WHERE l.is_completed), 0) AS revenue
FROM crm_product p
LEFT JOIN analytics.v_order_lines l ON l.product_sku = p.sku
GROUP BY p.id;

-- ------------------------------------------------------------------ v_interactions
CREATE VIEW analytics.v_interactions AS
SELECT
    t.id                                                   AS interaction_id,
    (t.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')         AS interaction_date,
    CASE t.channel WHEN 'email' THEN 'Email' WHEN 'phone' THEN 'Điện thoại'
                   WHEN 'chat' THEN 'Chat' WHEN 'in_person' THEN 'Trực tiếp' END AS channel,
    t.customer_id,
    c.name                                                 AS customer_name,
    t.is_ai_generated,
    (TRIM(t.final_reply) <> '')                            AS is_answered,
    COALESCE(analytics.staff_name(u), 'Chưa phân công')    AS staff_name
FROM crm_interactionlog t
JOIN crm_customer c   ON c.id = t.customer_id
LEFT JOIN auth_user u ON u.id = t.staff_id;

-- ------------------------------------------------------------------ v_customer_rfm (phân tích bổ sung)
-- Chấm điểm 1–5 cho từng khách đã có đơn Hoàn thành (chia 5 nhóm bằng nhau – NTILE):
--   R (Recency)   mua gần đây hơn  -> điểm cao hơn
--   F (Frequency) nhiều đơn hơn    -> điểm cao hơn
--   M (Monetary)  chi tiêu nhiều   -> điểm cao hơn
-- rồi gom thành phân khúc để biết nên giữ chân / kích hoạt lại / chăm sóc nhóm nào.
CREATE VIEW analytics.v_customer_rfm AS
WITH base AS (
    SELECT customer_id, customer_name, customer_type, customer_source, staff_name, customer_status_label,
           ((now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - last_order_date::date) AS recency_days,
           completed_orders                                AS frequency,
           total_spent                                     AS monetary
    FROM analytics.v_customers
    WHERE completed_orders > 0
), scored AS (
    SELECT base.*,
           NTILE(5) OVER (ORDER BY recency_days DESC, customer_id) AS r_score,
           NTILE(5) OVER (ORDER BY frequency, customer_id)         AS f_score,
           NTILE(5) OVER (ORDER BY monetary, customer_id)          AS m_score
    FROM base
)
SELECT
    scored.*,
    (r_score::text || f_score::text || m_score::text)     AS rfm_code,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '1. VIP'
        WHEN r_score >= 3 AND f_score >= 3                  THEN '2. Trung thành'
        WHEN r_score >= 4 AND f_score <= 2                  THEN '3. Khách mới'
        WHEN r_score <= 2 AND f_score >= 3                  THEN '4. Có nguy cơ rời bỏ'
        WHEN r_score <= 2 AND f_score <= 2                  THEN '6. Ngủ đông'
        ELSE '5. Cần nuôi dưỡng'
    END                                                    AS rfm_segment
FROM scored;

COMMENT ON VIEW analytics.v_customer_rfm IS 'Phân khúc RFM của khách đã mua – điểm 1–5 theo NTILE';

-- ------------------------------------------------------------------ v_cohort (phân tích bổ sung)
-- Cohort = nhóm khách có đơn Hoàn thành ĐẦU TIÊN trong cùng một tháng.
-- month_number = số tháng tính từ tháng đầu tiên (0 = tháng mua đầu tiên).
-- retention_rate = tỉ lệ khách của cohort còn mua lại ở tháng đó.
CREATE VIEW analytics.v_cohort AS
WITH buys AS (
    SELECT customer_id, date_trunc('month', order_date)::date AS active_month
    FROM analytics.v_orders
    WHERE is_completed
    GROUP BY 1, 2
), firsts AS (
    SELECT customer_id, MIN(active_month) AS cohort_month
    FROM buys
    GROUP BY 1
), sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM firsts
    GROUP BY 1
)
SELECT
    f.cohort_month,
    to_char(f.cohort_month, 'YYYY-MM')                     AS cohort_label,
    ((EXTRACT(YEAR FROM b.active_month) - EXTRACT(YEAR FROM f.cohort_month)) * 12
      + EXTRACT(MONTH FROM b.active_month) - EXTRACT(MONTH FROM f.cohort_month))::int AS month_number,
    COUNT(*)                                               AS active_customers,
    s.cohort_size,
    ROUND(COUNT(*)::numeric / s.cohort_size, 4)            AS retention_rate
FROM buys b
JOIN firsts f ON f.customer_id = b.customer_id
JOIN sizes s  ON s.cohort_month = f.cohort_month
GROUP BY f.cohort_month, b.active_month, s.cohort_size;

COMMENT ON VIEW analytics.v_cohort IS 'Tỉ lệ khách quay lại mua theo tháng mua đầu tiên (cohort retention)';

COMMIT;

-- =====================================================================================
-- VERIFY – đối chiếu view với bảng gốc. Mọi dòng phải có ket_qua = 'OK'
-- =====================================================================================
SELECT 'Số dòng v_order_lines = crm_orderitem' AS kiem_tra,
       (SELECT COUNT(*) FROM analytics.v_order_lines) AS view_value,
       (SELECT COUNT(*) FROM crm_orderitem)           AS goc_value,
       CASE WHEN (SELECT COUNT(*) FROM analytics.v_order_lines) = (SELECT COUNT(*) FROM crm_orderitem)
            THEN 'OK' ELSE 'LECH' END AS ket_qua
UNION ALL
SELECT 'Số đơn v_orders = số đơn có sản phẩm',
       (SELECT COUNT(*) FROM analytics.v_orders),
       (SELECT COUNT(DISTINCT order_id) FROM crm_orderitem),
       CASE WHEN (SELECT COUNT(*) FROM analytics.v_orders) = (SELECT COUNT(DISTINCT order_id) FROM crm_orderitem)
            THEN 'OK' ELSE 'LECH' END
UNION ALL
SELECT 'Số khách v_customers = crm_customer',
       (SELECT COUNT(*) FROM analytics.v_customers),
       (SELECT COUNT(*) FROM crm_customer),
       CASE WHEN (SELECT COUNT(*) FROM analytics.v_customers) = (SELECT COUNT(*) FROM crm_customer)
            THEN 'OK' ELSE 'LECH' END
UNION ALL
SELECT 'Tổng doanh thu (đơn Hoàn thành)',
       (SELECT SUM(line_total) FROM analytics.v_order_lines WHERE is_completed),
       (SELECT SUM(i.quantity * i.unit_price) FROM crm_orderitem i
          JOIN crm_order o ON o.id = i.order_id WHERE o.status = 'completed'),
       CASE WHEN (SELECT SUM(line_total) FROM analytics.v_order_lines WHERE is_completed)
               = (SELECT SUM(i.quantity * i.unit_price) FROM crm_orderitem i
                    JOIN crm_order o ON o.id = i.order_id WHERE o.status = 'completed')
            THEN 'OK' ELSE 'LECH' END
UNION ALL
SELECT 'Tổng chi tiêu v_customers = tổng doanh thu',
       (SELECT SUM(total_spent) FROM analytics.v_customers),
       (SELECT SUM(line_total) FROM analytics.v_order_lines WHERE is_completed),
       CASE WHEN (SELECT SUM(total_spent) FROM analytics.v_customers)
               = (SELECT SUM(line_total) FROM analytics.v_order_lines WHERE is_completed)
            THEN 'OK' ELSE 'LECH' END
UNION ALL
SELECT 'Tổng chi tiêu v_customer_rfm = tổng doanh thu',
       (SELECT SUM(monetary) FROM analytics.v_customer_rfm),
       (SELECT SUM(line_total) FROM analytics.v_order_lines WHERE is_completed),
       CASE WHEN (SELECT SUM(monetary) FROM analytics.v_customer_rfm)
               = (SELECT SUM(line_total) FROM analytics.v_order_lines WHERE is_completed)
            THEN 'OK' ELSE 'LECH' END
UNION ALL
SELECT 'Khách tháng 0 của v_cohort = số khách có đơn Hoàn thành',
       (SELECT SUM(active_customers) FROM analytics.v_cohort WHERE month_number = 0),
       (SELECT COUNT(DISTINCT customer_id) FROM analytics.v_orders WHERE is_completed),
       CASE WHEN (SELECT SUM(active_customers) FROM analytics.v_cohort WHERE month_number = 0)
               = (SELECT COUNT(DISTINCT customer_id) FROM analytics.v_orders WHERE is_completed)
            THEN 'OK' ELSE 'LECH' END;
