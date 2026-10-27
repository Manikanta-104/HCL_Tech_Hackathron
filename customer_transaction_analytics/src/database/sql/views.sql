-- ==========================================================================
-- Reporting views
-- These flatten the star schema so KPI queries and the dashboard stay short.
-- ==========================================================================

-- One wide row per transaction: fact + customer + merchant + risk
CREATE VIEW vw_transaction_details AS
SELECT
    f.transaction_id,
    f.customer_id,
    c.customer_name,
    c.segment,
    c.home_location_id,
    c.preferred_channel,
    f.merchant_id,
    m.merchant_name,
    m.merchant_category,
    m.merchant_risk_level,
    f.is_registered_merchant,
    f.is_high_risk_merchant,
    f.is_category_mismatch,
    f.location_id,
    f.time_id,
    f.amount,
    f.category,
    f.channel,
    f.channel_group,
    f.txn_datetime,
    f.txn_date,
    f.txn_hour,
    f.day_of_week,
    f.day_of_week_num,
    f.month,
    f.month_num,
    f.year,
    f.year_month,
    f.is_weekend,
    f.time_bucket,
    f.amount_band,
    f.customer_txn_seq,
    f.prior_txn_count,
    f.prior_avg_amount,
    f.hours_since_prev_txn,
    f.merchant_frequency,
    f.customer_merchant_visit_no,
    f.is_repeat_merchant,
    f.is_new_category,
    f.is_home_location,
    f.is_new_location,
    f.location_changed,
    f.is_digital,
    f.is_preferred_channel,
    f.channel_changed,
    COALESCE(r.risk_score, 0)       AS risk_score,
    COALESCE(r.risk_level, 'None')  AS risk_level,
    COALESCE(r.rules_triggered, 0)  AS rules_triggered,
    COALESCE(r.rule_codes, '')      AS rule_codes
FROM fact_transaction f
JOIN dim_customer c          ON c.customer_id = f.customer_id
JOIN dim_merchant m          ON m.merchant_id = f.merchant_id
LEFT JOIN transaction_risk r ON r.transaction_id = f.transaction_id;

-- Alerts with rule metadata and transaction context
CREATE VIEW vw_alert_details AS
SELECT
    a.alert_id,
    a.transaction_id,
    a.customer_id,
    c.customer_name,
    c.segment,
    a.rule_code,
    ar.rule_name,
    a.severity,
    a.severity_weight,
    a.details,
    f.txn_datetime,
    f.txn_date,
    f.amount,
    f.category,
    f.channel,
    f.location_id,
    f.merchant_id,
    m.merchant_name,
    m.merchant_risk_level,
    r.risk_score,
    r.risk_level
FROM anomaly_alert a
JOIN anomaly_rule ar         ON ar.rule_code = a.rule_code
JOIN fact_transaction f      ON f.transaction_id = a.transaction_id
JOIN dim_customer c          ON c.customer_id = a.customer_id
JOIN dim_merchant m          ON m.merchant_id = f.merchant_id
JOIN transaction_risk r      ON r.transaction_id = a.transaction_id;

-- Customer 360: profile plus alert summary
CREATE VIEW vw_customer_360 AS
SELECT
    c.*,
    COALESCE(al.alert_count, 0)      AS alert_count,
    COALESCE(al.high_alerts, 0)      AS high_alerts,
    COALESCE(rk.max_risk_score, 0)   AS max_risk_score
FROM dim_customer c
LEFT JOIN (
    SELECT customer_id,
           COUNT(*)                                        AS alert_count,
           SUM(CASE WHEN severity = 'High' THEN 1 ELSE 0 END) AS high_alerts
    FROM anomaly_alert
    GROUP BY customer_id
) al ON al.customer_id = c.customer_id
LEFT JOIN (
    SELECT customer_id, MAX(risk_score) AS max_risk_score
    FROM transaction_risk
    GROUP BY customer_id
) rk ON rk.customer_id = c.customer_id;
