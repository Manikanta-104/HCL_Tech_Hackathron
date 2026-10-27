-- ==========================================================================
-- Customer Transaction Analytics Platform: SQLite schema
-- --------------------------------------------------------------------------
-- Star schema:
--   fact_transaction  (one row per transaction, with engineered features)
--   dim_customer      (customer master + behaviour profile)
--   dim_time          (calendar and hour attributes)
--   dim_merchant      (merchant master + activity statistics)
--   dim_location      (derived shared location domain)
-- Analytics tables:
--   anomaly_rule, anomaly_alert, transaction_risk
-- Operational tables:
--   pipeline_run, data_quality_log
-- The script is idempotent: running it again rebuilds the database.
-- ==========================================================================

PRAGMA foreign_keys = OFF;

DROP VIEW  IF EXISTS vw_transaction_details;
DROP VIEW  IF EXISTS vw_customer_360;
DROP VIEW  IF EXISTS vw_alert_details;

DROP TABLE IF EXISTS anomaly_alert;
DROP TABLE IF EXISTS transaction_risk;
DROP TABLE IF EXISTS anomaly_rule;
DROP TABLE IF EXISTS fact_transaction;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_time;
DROP TABLE IF EXISTS dim_merchant;
DROP TABLE IF EXISTS dim_location;
DROP TABLE IF EXISTS data_quality_log;
DROP TABLE IF EXISTS pipeline_run;

PRAGMA foreign_keys = ON;

-- --------------------------------------------------------------------------
-- Dimensions
-- --------------------------------------------------------------------------
CREATE TABLE dim_location (
    location_id      TEXT PRIMARY KEY,
    txn_count        INTEGER NOT NULL DEFAULT 0,
    total_value      REAL    NOT NULL DEFAULT 0,
    home_customers   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE dim_customer (
    customer_id                 TEXT PRIMARY KEY,
    customer_name               TEXT NOT NULL,
    segment                     TEXT NOT NULL,
    home_location_id            TEXT REFERENCES dim_location(location_id),
    preferred_channel           TEXT NOT NULL,
    txn_count                   INTEGER NOT NULL DEFAULT 0,
    total_spend                 REAL    NOT NULL DEFAULT 0,
    avg_spend                   REAL,
    median_spend                REAL,
    max_spend                   REAL,
    distinct_merchants          INTEGER NOT NULL DEFAULT 0,
    distinct_locations          INTEGER NOT NULL DEFAULT 0,
    distinct_categories         INTEGER NOT NULL DEFAULT 0,
    repeat_merchant_txns        INTEGER NOT NULL DEFAULT 0,
    home_location_txns          INTEGER NOT NULL DEFAULT 0,
    top_location_txns           INTEGER NOT NULL DEFAULT 0,
    digital_txns                INTEGER NOT NULL DEFAULT 0,
    preferred_channel_txns      INTEGER NOT NULL DEFAULT 0,
    high_risk_merchant_txns     INTEGER NOT NULL DEFAULT 0,
    category_mismatch_txns      INTEGER NOT NULL DEFAULT 0,
    observed_preferred_channel  TEXT,
    preferred_location          TEXT,
    favourite_category          TEXT,
    first_txn_date              TEXT,
    last_txn_date               TEXT,
    repeat_merchant_ratio       REAL,
    geo_consistency_index       REAL,
    home_location_ratio         REAL,
    digital_share               REAL,
    channel_loyalty_ratio       REAL,
    is_active                   INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    CHECK (segment IN ('Student', 'Standard', 'Premium', 'Unknown')),
    CHECK (preferred_channel IN ('Digital', 'Branch', 'ATM', 'Unknown'))
);

CREATE TABLE dim_time (
    time_id       TEXT PRIMARY KEY,
    txn_date      TEXT    NOT NULL,          -- ISO date YYYY-MM-DD
    day_of_week   TEXT    NOT NULL,
    month         TEXT    NOT NULL,
    year          INTEGER NOT NULL,
    hour_of_day   INTEGER NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23)
);

CREATE TABLE dim_merchant (
    merchant_id             TEXT PRIMARY KEY,
    merchant_name           TEXT    NOT NULL,
    merchant_category       TEXT    NOT NULL,
    merchant_risk_level     TEXT    NOT NULL,
    is_registered           INTEGER NOT NULL DEFAULT 1 CHECK (is_registered IN (0, 1)),
    txn_count               INTEGER NOT NULL DEFAULT 0,
    unique_customers        INTEGER NOT NULL DEFAULT 0,
    total_value             REAL    NOT NULL DEFAULT 0,
    avg_value               REAL,
    primary_txn_category    TEXT,
    category_mismatch_txns  INTEGER NOT NULL DEFAULT 0,
    category_match_ratio    REAL,
    CHECK (merchant_risk_level IN ('Low', 'Medium', 'High', 'Unknown'))
);

-- --------------------------------------------------------------------------
-- Fact
-- --------------------------------------------------------------------------
CREATE TABLE fact_transaction (
    transaction_id              TEXT PRIMARY KEY,
    customer_id                 TEXT NOT NULL REFERENCES dim_customer(customer_id),
    merchant_id                 TEXT NOT NULL REFERENCES dim_merchant(merchant_id),
    time_id                     TEXT NOT NULL REFERENCES dim_time(time_id),
    location_id                 TEXT NOT NULL REFERENCES dim_location(location_id),
    amount                      REAL NOT NULL CHECK (amount > 0),
    category                    TEXT NOT NULL,
    channel                     TEXT NOT NULL,
    -- time features
    txn_datetime                TEXT NOT NULL,   -- ISO timestamp
    txn_date                    TEXT NOT NULL,
    txn_hour                    INTEGER NOT NULL,
    day_of_week                 TEXT NOT NULL,
    day_of_week_num             INTEGER NOT NULL,
    month                       TEXT NOT NULL,
    month_num                   INTEGER NOT NULL,
    year                        INTEGER NOT NULL,
    year_month                  TEXT NOT NULL,
    is_weekend                  INTEGER NOT NULL,
    time_bucket                 TEXT NOT NULL,
    -- amount features
    amount_band                 TEXT NOT NULL,
    category_value_share        REAL,
    -- customer history features
    customer_txn_seq            INTEGER NOT NULL,
    prior_txn_count             INTEGER NOT NULL,
    prior_avg_amount            REAL,
    hours_since_prev_txn        REAL,
    prev_location               TEXT,
    prev_channel                TEXT,
    prev_merchant               TEXT,
    -- merchant features
    is_registered_merchant      INTEGER NOT NULL,
    is_high_risk_merchant       INTEGER NOT NULL,
    is_category_mismatch        INTEGER NOT NULL,
    merchant_frequency          INTEGER NOT NULL,
    merchant_unique_customers   INTEGER NOT NULL,
    customer_merchant_visit_no  INTEGER NOT NULL,
    is_repeat_merchant          INTEGER NOT NULL,
    is_new_category             INTEGER NOT NULL,
    -- geo features
    is_home_location            INTEGER NOT NULL,
    location_frequency          INTEGER NOT NULL,
    customer_location_visit_no  INTEGER NOT NULL,
    is_new_location             INTEGER NOT NULL,
    location_changed            INTEGER NOT NULL,
    -- channel features
    is_digital                  INTEGER NOT NULL,
    channel_group               TEXT NOT NULL,
    is_preferred_channel        INTEGER NOT NULL,
    channel_changed             INTEGER NOT NULL
);

CREATE INDEX idx_fact_customer ON fact_transaction(customer_id);
CREATE INDEX idx_fact_time     ON fact_transaction(time_id);
CREATE INDEX idx_fact_date     ON fact_transaction(txn_date);
CREATE INDEX idx_fact_channel  ON fact_transaction(channel);
CREATE INDEX idx_fact_merchant ON fact_transaction(merchant_id);

-- --------------------------------------------------------------------------
-- Anomaly detection
-- --------------------------------------------------------------------------
CREATE TABLE anomaly_rule (
    rule_code        TEXT PRIMARY KEY,
    rule_name        TEXT NOT NULL,
    description      TEXT NOT NULL,
    severity         TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High')),
    severity_weight  INTEGER NOT NULL
);

CREATE TABLE anomaly_alert (
    alert_id         TEXT PRIMARY KEY,
    transaction_id   TEXT NOT NULL REFERENCES fact_transaction(transaction_id),
    customer_id      TEXT NOT NULL REFERENCES dim_customer(customer_id),
    rule_code        TEXT NOT NULL REFERENCES anomaly_rule(rule_code),
    severity         TEXT NOT NULL,
    severity_weight  INTEGER NOT NULL,
    details          TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_alert_customer ON anomaly_alert(customer_id);
CREATE INDEX idx_alert_rule     ON anomaly_alert(rule_code);

CREATE TABLE transaction_risk (
    transaction_id   TEXT PRIMARY KEY REFERENCES fact_transaction(transaction_id),
    customer_id      TEXT NOT NULL REFERENCES dim_customer(customer_id),
    rules_triggered  INTEGER NOT NULL,
    risk_score       INTEGER NOT NULL,
    risk_level       TEXT NOT NULL CHECK (risk_level IN ('None', 'Low', 'Medium', 'High')),
    rule_codes       TEXT
);

-- --------------------------------------------------------------------------
-- Operational metadata
-- --------------------------------------------------------------------------
CREATE TABLE pipeline_run (
    run_id                TEXT PRIMARY KEY,
    started_at            TEXT NOT NULL,
    finished_at           TEXT,
    status                TEXT NOT NULL,
    raw_rows              INTEGER,
    clean_transactions    INTEGER,
    rejected_records      INTEGER,
    alerts_generated      INTEGER,
    duration_seconds      REAL,
    detected_relationships TEXT
);

CREATE TABLE data_quality_log (
    log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT NOT NULL REFERENCES pipeline_run(run_id),
    table_name     TEXT NOT NULL,
    check_name     TEXT NOT NULL,
    rows_affected  INTEGER NOT NULL,
    action         TEXT NOT NULL
);
