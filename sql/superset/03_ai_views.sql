-- =====================================================================================
-- TH2 · 03 – Schema `ai`: view CHỈ ĐỌC kết quả mô hình AI cho Apache Superset
-- =====================================================================================
-- Nguồn: bảng app insights (insights_modelrun, insights_revenueforecast, insights_churnscore,
--        insights_sentimentresult, insights_sentimentlabel) do `python manage.py run_ai_pipeline` ghi.
-- Mỗi view chỉ lấy batch THÀNH CÔNG mới nhất của từng module; batch "demo" (seed_ai_demo) chỉ dùng khi
-- module đó chưa có batch thật. Cấu trúc theo docs/th2/HOP_DONG_DU_LIEU.md mục 7.
--
-- Chạy SAU 01 và 02, trên CSDL TH2:
--   docker compose exec db psql -U smartcrm -d smartcrm_th2 -v ON_ERROR_STOP=1 -f /sql/03_ai_views.sql
-- Chạy lại nhiều lần không sao. Không cần chạy lại sau mỗi lần run_ai_pipeline (view tự lấy batch mới).
-- =====================================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS ai;
COMMENT ON SCHEMA ai IS 'TH2 – view chỉ đọc kết quả mô hình AI cho Superset';

DROP VIEW IF EXISTS ai.interaction_sentiment, ai.churn_score, ai.revenue_forecast, ai.model_run,
    ai.latest_batch CASCADE;

-- Batch thành công mới nhất của từng module (ưu tiên batch thật hơn batch demo)
CREATE VIEW ai.latest_batch AS
SELECT DISTINCT ON (module) module, batch
FROM insights_modelrun
WHERE status = 'success'
ORDER BY module, (batch = 'demo'), finished_at DESC;

CREATE OR REPLACE FUNCTION ai.method_label(method text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE method
        WHEN 'seasonal_naive'      THEN 'Cùng kỳ năm trước'
        WHEN 'holt_winters'        THEN 'Holt-Winters'
        WHEN 'sarima'              THEN 'SARIMA'
        WHEN 'rfm_rule'            THEN 'Luật RFM'
        WHEN 'logistic_regression' THEN 'Logistic Regression'
        WHEN 'random_forest'       THEN 'Random Forest'
        WHEN 'keyword'             THEN 'Từ điển từ khoá'
        WHEN 'gemini'              THEN 'LLM Gemini'
        ELSE method END
$$;

CREATE OR REPLACE FUNCTION ai.sentiment_label(label text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE label WHEN 'positive' THEN 'Tích cực' WHEN 'neutral' THEN 'Trung lập'
                      WHEN 'negative' THEN 'Tiêu cực' END
$$;

-- ------------------------------------------------------------------ model_run
CREATE VIEW ai.model_run AS
SELECT
    r.batch,
    r.module,
    CASE r.module WHEN 'forecast' THEN 'Dự báo doanh thu' WHEN 'churn' THEN 'Dự đoán khách rời bỏ'
                  WHEN 'sentiment' THEN 'Phân tích cảm xúc' END            AS module_label,
    r.method,
    ai.method_label(r.method)                                              AS method_label,
    r.is_selected,
    (r.finished_at AT TIME ZONE 'Asia/Ho_Chi_Minh')                        AS finished_at,
    (r.metrics ->> 'mae')::numeric                                         AS mae,
    (r.metrics ->> 'rmse')::numeric                                        AS rmse,
    (r.metrics ->> 'mape')::numeric                                        AS mape,
    (r.metrics ->> 'auc')::numeric                                         AS auc,
    (r.metrics ->> 'precision')::numeric                                   AS precision,
    (r.metrics ->> 'recall')::numeric                                      AS recall,
    (r.metrics ->> 'f1')::numeric                                          AS f1,
    (r.metrics ->> 'accuracy')::numeric                                    AS accuracy,
    (r.metrics ->> 'macro_f1')::numeric                                    AS macro_f1,
    (r.metrics ->> 'n_train')::int                                         AS n_train,
    COALESCE((r.metrics ->> 'n_test')::int, (r.metrics ->> 'n_eval')::int) AS n_test,
    (r.metrics ->> 'avg_latency_ms')::numeric                              AS avg_latency_ms,
    (r.batch = 'demo')                                                     AS is_demo
FROM insights_modelrun r
JOIN ai.latest_batch b ON b.module = r.module AND b.batch = r.batch
WHERE r.status = 'success';

COMMENT ON VIEW ai.model_run IS 'Chỉ số đánh giá các phương pháp, batch mới nhất mỗi module';

-- ------------------------------------------------------------------ revenue_forecast
CREATE VIEW ai.revenue_forecast AS
SELECT
    f.month,
    f.kind,
    CASE f.kind WHEN 'history' THEN 'Lịch sử' WHEN 'backtest' THEN 'Kiểm tra lại'
                WHEN 'future' THEN 'Dự báo' END                            AS kind_label,
    r.method,
    ai.method_label(r.method)                                              AS method_label,
    r.is_selected,
    f.actual,
    f.forecast,
    f.lower,
    f.upper,
    r.batch
FROM insights_revenueforecast f
JOIN insights_modelrun r ON r.id = f.run_id AND r.status = 'success'
JOIN ai.latest_batch b   ON b.module = r.module AND b.batch = r.batch;

COMMENT ON VIEW ai.revenue_forecast IS 'Doanh thu tháng: thực tế, dự báo kiểm tra lại 6 tháng, dự báo 6 tháng tới';

-- ------------------------------------------------------------------ churn_score
CREATE VIEW ai.churn_score AS
SELECT
    s.customer_id,
    c.customer_name,
    c.customer_type,
    c.customer_source,
    c.staff_name,
    c.last_order_date,
    c.total_spent,
    r.method,
    ai.method_label(r.method)                                              AS method_label,
    r.is_selected,
    s.probability,
    s.risk_band,
    CASE s.risk_band WHEN 'high' THEN '1. Cao' WHEN 'medium' THEN '2. Trung bình'
                     ELSE '3. Thấp' END                                    AS risk_label,
    r.batch
FROM insights_churnscore s
JOIN insights_modelrun r     ON r.id = s.run_id AND r.status = 'success'
JOIN ai.latest_batch b       ON b.module = r.module AND b.batch = r.batch
JOIN analytics.v_customers c ON c.customer_id = s.customer_id;

COMMENT ON VIEW ai.churn_score IS 'Xác suất rời bỏ từng khách tại ngày tham chiếu; không có email/SĐT';

-- ------------------------------------------------------------------ interaction_sentiment
CREATE VIEW ai.interaction_sentiment AS
SELECT
    t.interaction_id,
    t.interaction_date,
    t.channel,
    t.customer_name,
    r.method,
    ai.method_label(r.method)                                              AS method_label,
    r.is_selected,
    ai.sentiment_label(s.label)                                            AS label_pred,
    ai.sentiment_label(l.label)                                            AS label_true,
    (s.label = l.label)                                                    AS is_correct,
    s.confidence,
    s.latency_ms,
    r.batch
FROM insights_sentimentresult s
JOIN insights_modelrun r        ON r.id = s.run_id AND r.status = 'success'
JOIN ai.latest_batch b          ON b.module = r.module AND b.batch = r.batch
JOIN analytics.v_interactions t ON t.interaction_id = s.interaction_id
LEFT JOIN insights_sentimentlabel l ON l.interaction_id = s.interaction_id;

COMMENT ON VIEW ai.interaction_sentiment IS 'Cảm xúc dự đoán và nhãn đúng của từng tin nhắn; không có nội dung tin nhắn';

-- ------------------------------------------------------------------ quyền cho Superset
-- superset_ro (tạo ở file 02) chỉ đọc được schema ai, không đọc bảng gốc insights_*
GRANT USAGE ON SCHEMA ai TO superset_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA ai TO superset_ro;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA ai TO superset_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA ai GRANT SELECT ON TABLES TO superset_ro;

COMMIT;

-- ------------------------------------------------------------------ VERIFY
SELECT 'Mỗi module có đúng 1 phương pháp được chọn' AS kiem_tra,
       (SELECT string_agg(module || '=' || n, ', ') FROM
           (SELECT module, COUNT(*) FILTER (WHERE is_selected) AS n FROM ai.model_run GROUP BY module) x) AS ket_qua,
       CASE WHEN NOT EXISTS (SELECT 1 FROM ai.model_run GROUP BY module
                             HAVING COUNT(*) FILTER (WHERE is_selected) <> 1)
            THEN 'OK' ELSE 'LECH' END AS trang_thai
UNION ALL
SELECT 'Doanh thu thực tế trong ai.revenue_forecast = analytics.v_order_lines',
       (SELECT SUM(actual)::text FROM ai.revenue_forecast WHERE is_selected AND kind IN ('history', 'backtest')),
       CASE WHEN (SELECT SUM(actual) FROM ai.revenue_forecast WHERE is_selected AND kind IN ('history', 'backtest'))
               = (SELECT SUM(line_total) FROM analytics.v_order_lines WHERE is_completed
                    AND date_trunc('month', order_date)::date IN
                        (SELECT month FROM ai.revenue_forecast WHERE is_selected AND kind IN ('history', 'backtest')))
            THEN 'OK' ELSE 'LECH' END
UNION ALL
SELECT 'Mọi khách có đơn Hoàn thành đều có điểm rủi ro (phương pháp được chọn)',
       (SELECT COUNT(*)::text FROM ai.churn_score WHERE is_selected),
       CASE WHEN (SELECT COUNT(*) FROM ai.churn_score WHERE is_selected)
               = (SELECT COUNT(DISTINCT customer_id) FROM analytics.v_orders WHERE is_completed)
            THEN 'OK' ELSE 'LECH' END
UNION ALL
SELECT 'Mọi kết quả cảm xúc đều có nhãn đúng để chấm',
       (SELECT COUNT(*)::text FROM ai.interaction_sentiment),
       CASE WHEN NOT EXISTS (SELECT 1 FROM ai.interaction_sentiment WHERE label_true IS NULL)
            THEN 'OK' ELSE 'LECH' END
UNION ALL
SELECT 'superset_ro KHÔNG đọc được bảng gốc insights_modelrun',
       has_table_privilege('superset_ro', 'insights_modelrun', 'SELECT')::text,
       CASE WHEN NOT has_table_privilege('superset_ro', 'insights_modelrun', 'SELECT') THEN 'OK' ELSE 'LECH' END;
