-- ==========================================================================
-- KPI queries
-- --------------------------------------------------------------------------
-- Every query reads from "ft" (filtered transactions). At run time the KPI
-- engine puts a CTE in front of each query:
--
--     WITH ft AS (SELECT * FROM vw_transaction_details WHERE <filters>)
--
-- The batch pipeline uses no filters, the dashboard passes the sidebar
-- filters. One SQL file therefore serves both, so numbers always agree.
-- Each query starts with a "-- name:" line that the engine uses as its key.
-- ==========================================================================


-- name: kpi_overview
SELECT
    COUNT(*)                                                         AS total_transactions,
    COUNT(DISTINCT customer_id)                                      AS active_customers,
    COUNT(DISTINCT merchant_id)                                      AS active_merchants,
    ROUND(COALESCE(SUM(amount), 0), 2)                               AS total_value,
    ROUND(AVG(amount), 2)                                            AS avg_transaction_value,
    ROUND(100.0 * SUM(is_digital) / NULLIF(COUNT(*), 0), 2)          AS digital_share_pct,
    ROUND(100.0 * (COUNT(*) - COUNT(DISTINCT customer_id || '|' || merchant_id))
          / NULLIF(COUNT(*), 0), 2)                                  AS repeat_merchant_ratio_pct,
    SUM(CASE WHEN rules_triggered > 0 THEN 1 ELSE 0 END)             AS flagged_transactions,
    SUM(CASE WHEN risk_level = 'High' THEN 1 ELSE 0 END)             AS high_risk_transactions,
    ROUND(100.0 * SUM(is_high_risk_merchant) / NULLIF(COUNT(*), 0), 2) AS high_risk_merchant_share_pct,
    ROUND(100.0 * SUM(is_category_mismatch) / NULLIF(COUNT(*), 0), 2)  AS category_mismatch_pct,
    MIN(txn_date)                                                    AS first_date,
    MAX(txn_date)                                                    AS last_date
FROM ft;


-- ==========================================================================
-- 1. Customer segmentation
-- ==========================================================================

-- name: segmentation_by_segment
SELECT
    segment,
    COUNT(DISTINCT customer_id)                                         AS customers,
    COUNT(*)                                                            AS transactions,
    ROUND(SUM(amount), 2)                                               AS total_value,
    ROUND(AVG(amount), 2)                                               AS avg_txn_value,
    ROUND(SUM(amount) / COUNT(DISTINCT customer_id), 2)                 AS avg_spend_per_customer,
    ROUND(1.0 * COUNT(*) / COUNT(DISTINCT customer_id), 2)              AS txns_per_customer,
    ROUND(100.0 * SUM(amount) / (SELECT SUM(amount) FROM ft), 2)        AS value_share_pct,
    ROUND(100.0 * SUM(is_digital) / COUNT(*), 2)                        AS digital_share_pct
FROM ft
GROUP BY segment
ORDER BY total_value DESC;


-- name: customer_value_tiers
-- Customers ranked by spend into three equal sized tiers (NTILE), plus an
-- engagement tier based on how often they transact.
WITH customer_spend AS (
    SELECT
        customer_id,
        customer_name,
        segment,
        COUNT(*)      AS txn_count,
        SUM(amount)   AS total_spend,
        AVG(amount)   AS avg_spend,
        MAX(txn_date) AS last_txn_date
    FROM ft
    GROUP BY customer_id, customer_name, segment
),
ranked AS (
    SELECT *, NTILE(3) OVER (ORDER BY total_spend DESC) AS spend_tile
    FROM customer_spend
)
SELECT
    customer_id,
    customer_name,
    segment,
    txn_count,
    ROUND(total_spend, 2) AS total_spend,
    ROUND(avg_spend, 2)   AS avg_spend,
    last_txn_date,
    CASE spend_tile WHEN 1 THEN 'High Value' WHEN 2 THEN 'Mid Value' ELSE 'Low Value' END AS value_tier,
    CASE
        WHEN txn_count >= 4 THEN 'Frequent (4+)'
        WHEN txn_count >= 2 THEN 'Occasional (2-3)'
        ELSE 'One time (1)'
    END AS engagement_tier
FROM ranked
ORDER BY total_spend DESC;


-- name: value_tier_by_segment
WITH customer_spend AS (
    SELECT customer_id, segment, SUM(amount) AS total_spend
    FROM ft
    GROUP BY customer_id, segment
),
ranked AS (
    SELECT *, NTILE(3) OVER (ORDER BY total_spend DESC) AS spend_tile
    FROM customer_spend
)
SELECT
    CASE spend_tile WHEN 1 THEN 'High Value' WHEN 2 THEN 'Mid Value' ELSE 'Low Value' END AS value_tier,
    segment,
    COUNT(*)                   AS customers,
    ROUND(SUM(total_spend), 2) AS total_spend
FROM ranked
GROUP BY spend_tile, segment
ORDER BY spend_tile, segment;


-- ==========================================================================
-- 2. Peak transaction time analysis
-- ==========================================================================

-- name: peak_by_hour
SELECT
    txn_hour,
    COUNT(*)              AS transactions,
    ROUND(SUM(amount), 2) AS total_value,
    ROUND(AVG(amount), 2) AS avg_value
FROM ft
GROUP BY txn_hour
ORDER BY txn_hour;


-- name: peak_by_time_bucket
SELECT
    time_bucket,
    COUNT(*)                                                    AS transactions,
    ROUND(SUM(amount), 2)                                       AS total_value,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM ft), 2)      AS txn_share_pct
FROM ft
GROUP BY time_bucket
ORDER BY MIN(txn_hour);


-- name: peak_by_day_of_week
SELECT
    day_of_week,
    COUNT(*)              AS transactions,
    ROUND(SUM(amount), 2) AS total_value,
    ROUND(AVG(amount), 2) AS avg_value
FROM ft
GROUP BY day_of_week, day_of_week_num
ORDER BY day_of_week_num;


-- name: hour_day_heatmap
SELECT day_of_week, day_of_week_num, txn_hour, COUNT(*) AS transactions
FROM ft
GROUP BY day_of_week, day_of_week_num, txn_hour
ORDER BY day_of_week_num, txn_hour;


-- name: daily_trend
SELECT
    txn_date,
    COUNT(*)                                             AS transactions,
    ROUND(SUM(amount), 2)                                AS total_value,
    SUM(CASE WHEN rules_triggered > 0 THEN 1 ELSE 0 END) AS flagged_transactions
FROM ft
GROUP BY txn_date
ORDER BY txn_date;


-- ==========================================================================
-- 3. Repeat merchant ratio
--    Share of transactions made at a merchant the same customer already
--    used in the selected period: (transactions - unique customer/merchant
--    pairs) / transactions
-- ==========================================================================

-- name: repeat_merchant_overall
WITH pairs AS (
    SELECT customer_id, merchant_id, COUNT(*) AS visits
    FROM ft
    GROUP BY customer_id, merchant_id
)
SELECT
    SUM(visits)                                                 AS transactions,
    COUNT(*)                                                    AS unique_customer_merchant_pairs,
    SUM(visits) - COUNT(*)                                      AS repeat_transactions,
    ROUND(100.0 * (SUM(visits) - COUNT(*)) / NULLIF(SUM(visits), 0), 2) AS repeat_merchant_ratio_pct,
    COUNT(DISTINCT CASE WHEN visits > 1 THEN customer_id END)   AS customers_with_repeat_merchant
FROM pairs;


-- name: repeat_merchant_by_segment
WITH pairs AS (
    SELECT segment, customer_id, merchant_id, COUNT(*) AS visits
    FROM ft
    GROUP BY segment, customer_id, merchant_id
)
SELECT
    segment,
    SUM(visits)                                                         AS transactions,
    SUM(visits) - COUNT(*)                                              AS repeat_transactions,
    ROUND(100.0 * (SUM(visits) - COUNT(*)) / NULLIF(SUM(visits), 0), 2) AS repeat_merchant_ratio_pct
FROM pairs
GROUP BY segment
ORDER BY repeat_merchant_ratio_pct DESC;


-- name: top_merchants
SELECT
    merchant_id,
    merchant_name,
    merchant_category,
    merchant_risk_level,
    COUNT(*)                                AS transactions,
    COUNT(DISTINCT customer_id)             AS unique_customers,
    COUNT(*) - COUNT(DISTINCT customer_id)  AS repeat_visits,
    ROUND(SUM(amount), 2)                   AS total_value,
    ROUND(AVG(amount), 2)                   AS avg_value
FROM ft
GROUP BY merchant_id, merchant_name, merchant_category, merchant_risk_level
ORDER BY transactions DESC, total_value DESC
LIMIT 10;


-- ==========================================================================
-- Merchant analytics (from the merchant master)
-- ==========================================================================

-- name: merchant_risk_exposure
-- How much activity goes to merchants of each risk rating
SELECT
    merchant_risk_level,
    COUNT(DISTINCT merchant_id)                                   AS merchants,
    COUNT(DISTINCT customer_id)                                   AS customers,
    COUNT(*)                                                      AS transactions,
    ROUND(SUM(amount), 2)                                         AS total_value,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM ft), 2)        AS txn_share_pct,
    ROUND(100.0 * SUM(amount) / (SELECT SUM(amount) FROM ft), 2)  AS value_share_pct
FROM ft
GROUP BY merchant_risk_level
ORDER BY CASE merchant_risk_level WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END;


-- name: merchant_category_summary
-- Activity per registered merchant category, and how often the transaction
-- category agrees with the category the merchant is registered under
WITH pairs AS (
    SELECT merchant_category, customer_id, merchant_id, COUNT(*) AS visits
    FROM ft
    GROUP BY merchant_category, customer_id, merchant_id
),
repeat_stats AS (
    SELECT merchant_category, SUM(visits) - COUNT(*) AS repeat_transactions
    FROM pairs
    GROUP BY merchant_category
)
SELECT
    ft.merchant_category,
    COUNT(DISTINCT ft.merchant_id)                                            AS merchants,
    COUNT(*)                                                                  AS transactions,
    ROUND(SUM(ft.amount), 2)                                                  AS total_value,
    ROUND(AVG(ft.amount), 2)                                                  AS avg_value,
    ROUND(100.0 * (1 - 1.0 * SUM(ft.is_category_mismatch) / COUNT(*)), 2)     AS category_match_pct,
    ROUND(100.0 * rs.repeat_transactions / COUNT(*), 2)                       AS repeat_merchant_ratio_pct
FROM ft
JOIN repeat_stats rs ON rs.merchant_category = ft.merchant_category
GROUP BY ft.merchant_category, rs.repeat_transactions
ORDER BY total_value DESC;


-- name: merchant_category_consistency
-- Registered merchant category (rows) against the category on the transaction
SELECT
    merchant_category,
    category AS transaction_category,
    COUNT(*) AS transactions
FROM ft
GROUP BY merchant_category, category
ORDER BY merchant_category, category;


-- ==========================================================================
-- 4. Geo-location consistency index (GCI)
--    For each customer with 2+ transactions: share of transactions made at
--    their most used location. 1.0 means always the same place. The index
--    is the average across those customers.
-- ==========================================================================

-- name: geo_consistency_overall
WITH customer_location AS (
    SELECT customer_id, location_id, COUNT(*) AS txns, SUM(is_home_location) AS home_txns
    FROM ft
    GROUP BY customer_id, location_id
),
per_customer AS (
    SELECT
        customer_id,
        SUM(txns)      AS txns,
        MAX(txns)      AS top_location_txns,
        COUNT(*)       AS distinct_locations,
        SUM(home_txns) AS home_txns
    FROM customer_location
    GROUP BY customer_id
)
SELECT
    COUNT(*)                                                                     AS customers,
    SUM(CASE WHEN txns >= 2 THEN 1 ELSE 0 END)                                   AS customers_with_history,
    ROUND(AVG(CASE WHEN txns >= 2 THEN 1.0 * top_location_txns / txns END), 4)   AS geo_consistency_index,
    ROUND(1.0 * SUM(home_txns) / NULLIF(SUM(txns), 0), 4)                        AS home_location_ratio,
    ROUND(AVG(CASE WHEN txns >= 2 THEN distinct_locations END), 2)               AS avg_locations_per_customer
FROM per_customer;


-- name: geo_consistency_by_segment
WITH customer_location AS (
    SELECT segment, customer_id, location_id, COUNT(*) AS txns
    FROM ft
    GROUP BY segment, customer_id, location_id
),
per_customer AS (
    SELECT segment, customer_id, SUM(txns) AS txns, MAX(txns) AS top_location_txns, COUNT(*) AS distinct_locations
    FROM customer_location
    GROUP BY segment, customer_id
)
SELECT
    segment,
    SUM(CASE WHEN txns >= 2 THEN 1 ELSE 0 END)                                   AS customers_with_history,
    ROUND(AVG(CASE WHEN txns >= 2 THEN 1.0 * top_location_txns / txns END), 4)   AS geo_consistency_index,
    ROUND(AVG(CASE WHEN txns >= 2 THEN distinct_locations END), 2)               AS avg_locations_per_customer
FROM per_customer
GROUP BY segment
ORDER BY segment;


-- name: geo_consistency_by_customer
WITH customer_location AS (
    SELECT customer_id, customer_name, segment, home_location_id, location_id,
           COUNT(*) AS txns, SUM(is_home_location) AS home_txns
    FROM ft
    GROUP BY customer_id, customer_name, segment, home_location_id, location_id
)
SELECT
    customer_id,
    customer_name,
    segment,
    home_location_id,
    SUM(txns)                                     AS transactions,
    COUNT(*)                                      AS distinct_locations,
    ROUND(1.0 * MAX(txns) / SUM(txns), 4)         AS geo_consistency_index,
    ROUND(1.0 * SUM(home_txns) / SUM(txns), 4)    AS home_location_ratio
FROM customer_location
GROUP BY customer_id, customer_name, segment, home_location_id
ORDER BY transactions DESC, geo_consistency_index ASC;


-- ==========================================================================
-- 5. Digital vs branch transaction mix
-- ==========================================================================

-- name: channel_mix
SELECT
    channel,
    COUNT(*)                                                      AS transactions,
    ROUND(SUM(amount), 2)                                         AS total_value,
    ROUND(AVG(amount), 2)                                         AS avg_value,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM ft), 2)        AS txn_share_pct,
    ROUND(100.0 * SUM(amount) / (SELECT SUM(amount) FROM ft), 2)  AS value_share_pct
FROM ft
GROUP BY channel
ORDER BY transactions DESC;


-- name: digital_vs_branch
SELECT
    SUM(CASE WHEN channel = 'Digital' THEN 1 ELSE 0 END)  AS digital_txns,
    SUM(CASE WHEN channel = 'Branch'  THEN 1 ELSE 0 END)  AS branch_txns,
    SUM(CASE WHEN channel = 'ATM'     THEN 1 ELSE 0 END)  AS atm_txns,
    ROUND(1.0 * SUM(CASE WHEN channel = 'Digital' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN channel = 'Branch' THEN 1 ELSE 0 END), 0), 2)       AS digital_to_branch_ratio,
    ROUND(100.0 * SUM(CASE WHEN channel = 'Digital' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN channel IN ('Digital', 'Branch') THEN 1 ELSE 0 END), 0), 2) AS digital_share_of_digital_branch_pct,
    ROUND(100.0 * SUM(is_digital) / NULLIF(COUNT(*), 0), 2)                         AS digital_share_pct,
    ROUND(100.0 * SUM(1 - is_digital) / NULLIF(COUNT(*), 0), 2)                     AS physical_share_pct
FROM ft;


-- name: channel_mix_by_segment
SELECT
    segment,
    channel,
    COUNT(*)                                                                      AS transactions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY segment), 2)        AS share_within_segment_pct
FROM ft
GROUP BY segment, channel
ORDER BY segment, channel;


-- name: channel_mix_by_month
SELECT
    year_month,
    channel,
    COUNT(*)                                                                      AS transactions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY year_month), 2)     AS share_within_month_pct
FROM ft
GROUP BY year_month, channel
ORDER BY year_month, channel;


-- name: preferred_vs_actual_channel
SELECT
    preferred_channel,
    channel AS actual_channel,
    COUNT(*) AS transactions
FROM ft
GROUP BY preferred_channel, channel
ORDER BY preferred_channel, channel;


-- ==========================================================================
-- Supporting analytics
-- ==========================================================================

-- name: category_spend
SELECT
    category,
    COUNT(*)                                                      AS transactions,
    ROUND(SUM(amount), 2)                                         AS total_value,
    ROUND(AVG(amount), 2)                                         AS avg_value,
    ROUND(100.0 * SUM(amount) / (SELECT SUM(amount) FROM ft), 2)  AS value_share_pct
FROM ft
GROUP BY category
ORDER BY total_value DESC;


-- name: amount_band_distribution
SELECT amount_band, COUNT(*) AS transactions, ROUND(SUM(amount), 2) AS total_value
FROM ft
GROUP BY amount_band
ORDER BY MIN(amount);


-- ==========================================================================
-- Anomaly analytics (alerts restricted to the filtered transactions)
-- ==========================================================================

-- name: alerts_by_rule
SELECT
    a.rule_code,
    a.rule_name,
    a.severity,
    COUNT(*)                         AS alerts,
    COUNT(DISTINCT a.customer_id)    AS customers_affected,
    ROUND(SUM(a.amount), 2)          AS value_at_risk
FROM vw_alert_details a
WHERE a.transaction_id IN (SELECT transaction_id FROM ft)
GROUP BY a.rule_code, a.rule_name, a.severity
ORDER BY alerts DESC;


-- name: risk_level_distribution
SELECT
    risk_level,
    COUNT(*)              AS transactions,
    ROUND(SUM(amount), 2) AS total_value
FROM ft
GROUP BY risk_level
ORDER BY CASE risk_level WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END;


-- name: alert_list
SELECT
    a.alert_id, a.txn_datetime, a.transaction_id, a.customer_id, a.customer_name, a.segment,
    a.rule_name, a.severity, a.amount, a.channel, a.location_id, a.merchant_id, a.merchant_name,
    a.merchant_risk_level, a.risk_score, a.risk_level, a.details
FROM vw_alert_details a
WHERE a.transaction_id IN (SELECT transaction_id FROM ft)
ORDER BY a.risk_score DESC, a.severity_weight DESC, a.txn_datetime DESC;


-- name: top_risky_customers
SELECT
    customer_id,
    customer_name,
    segment,
    COUNT(*)                                                    AS transactions,
    SUM(rules_triggered)                                        AS alerts,
    SUM(risk_score)                                             AS total_risk_score,
    MAX(risk_score)                                             AS max_risk_score,
    SUM(CASE WHEN risk_level = 'High' THEN 1 ELSE 0 END)        AS high_risk_txns
FROM ft
GROUP BY customer_id, customer_name, segment
HAVING SUM(rules_triggered) > 0
ORDER BY total_risk_score DESC, max_risk_score DESC
LIMIT 10;
