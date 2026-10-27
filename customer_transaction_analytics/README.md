# Customer Transaction Analytics Platform

A batch analytics platform that helps a retail bank understand how its customers transact, track business KPIs, spot unusual behaviour with clear business rules, and explore it all in an interactive dashboard.

Built with Python, Pandas, NumPy, SQLite, SQL, Streamlit and Plotly only. No machine learning, no cloud services, no external APIs.

---

## 1. Architecture

```
CSV Transaction Files (Landing Zone: data/raw)
                    │
                    ▼
Data Ingestion (Python + Pandas)
  read all CSVs, identify each table by its columns,
  validate schema, detect relationships automatically
                    │
                    ▼
Data Cleaning & Validation
  missing values, duplicate removal, invalid records,
  data type validation, date conversion, referential integrity
                    │
                    ▼
Merge (dimensions joined onto the transaction fact)
                    │
                    ▼
Feature Engineering
  transaction time, category, merchant frequency,
  geo features, channel features, customer profile
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
     KPI Engine        Rule-Based Anomaly Detection
   (SQL on SQLite)       (7 business rules)
          │                    │
          └─────────┬──────────┘
                    ▼
        SQLite (star schema + views)
                    │
                    ▼
        SQL queries calculate KPIs
                    │
                    ▼
     Streamlit Dashboard (Plotly charts)
  KPI cards · interactive charts · customer search · alerts · filters
```

The anomaly rules run on the engineered features in Pandas, then the curated data, alerts and risk scores are stored together in SQLite. Every KPI is then calculated with SQL, both for the batch reports and for the dashboard.

---

## 2. Folder structure

```
customer_transaction_analytics/
│
├── data/
│   ├── raw/                     Landing zone: source CSV files
│   ├── processed/               Cleaned tables, features, rejected records
│   └── output/                  SQLite database, KPI extracts, alerts
│
├── src/
│   ├── ingestion/
│   │   ├── schema_registry.py       Expected schema of every source table
│   │   ├── data_loader.py           Read CSVs, identify tables, validate schema
│   │   ├── relationship_detector.py Detect foreign keys and shared domains
│   │   └── data_merger.py           Join dimensions onto the fact table
│   ├── preprocessing/
│   │   ├── data_cleaner.py          All cleaning and validation rules
│   │   └── cleaning_report.py       Audit trail, quarantine, report writer
│   ├── features/
│   │   └── feature_engineering.py   Transaction, customer, merchant, location features
│   ├── database/
│   │   ├── sql/
│   │   │   ├── schema.sql           Tables, keys, constraints, indexes
│   │   │   ├── views.sql            Reporting views
│   │   │   └── kpi_queries.sql      Every KPI and analytics query
│   │   ├── db_manager.py            Connections and script execution
│   │   └── db_loader.py             Loads curated data into SQLite
│   ├── kpi/
│   │   ├── kpi_queries.py           Query library loader and filter builder
│   │   └── kpi_engine.py            Runs KPIs, exports CSVs and reports
│   ├── anomaly/
│   │   ├── rules.py                 Business rule catalogue
│   │   └── anomaly_detector.py      Runs rules, builds alerts and risk scores
│   ├── dashboard/
│   │   ├── app.py                   Streamlit entry point, sidebar, routing
│   │   ├── views.py                 The five dashboard pages
│   │   ├── charts.py                Plotly chart builders
│   │   ├── components.py            KPI cards, styling, formatting
│   │   └── data_access.py           Cached queries for the dashboard
│   └── utils/
│       ├── config.py                Paths, reference values, rule thresholds
│       ├── logger.py                Console and file logging
│       └── helpers.py               Shared helper functions
│
├── reports/                     Generated run reports (Markdown, JSON, log)
├── requirements.txt
├── README.md
└── main.py                      Pipeline entry point
```

---

## 3. Run instructions (VS Code)

### 3.1 One time setup

1. Open the `customer_transaction_analytics` folder in VS Code (File, Open Folder).
2. Open a terminal (Terminal, New Terminal). Make sure it opens in the project root.
3. Create and activate a virtual environment:

   **Windows (PowerShell)**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

   **macOS / Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. In VS Code press `Ctrl+Shift+P`, choose **Python: Select Interpreter** and pick the `.venv` interpreter.

### 3.2 Run the pipeline

```bash
python main.py
```

This runs all seven stages and creates the SQLite database, the processed files, the KPI extracts and the reports. A run on the sample data takes under a second.

### 3.3 Open the dashboard

```bash
streamlit run src/dashboard/app.py
```

Streamlit opens `http://localhost:8501` in your browser. Two shortcuts are also available:

```bash
python main.py --dashboard        # run the pipeline, then open the dashboard
python main.py --dashboard-only   # open the dashboard on the existing database
```

### 3.4 Use your own data

Drop new CSV files into `data/raw/` and run `python main.py` again. File names do not matter: each file is matched to a table by its columns. Several files for the same table (for example monthly drops) are stacked automatically. The database is fully rebuilt on every run.

---

## 4. Source data and detected relationships

| File | Table | Rows | Primary key | Content |
| --- | --- | --- | --- | --- |
| Customers.csv | customers | 60 | CustomerID | name, segment, home location, preferred channel |
| Merchants.csv | merchants | 60 | MerchantID | name, registered category, merchant risk rating (Low, Medium, High) |
| Time.csv | time | 60 | TimeID | date, weekday, month, hour |
| Transactions.csv | transactions | 100 | TransactionID | amount, category, channel and the four keys above |

Relationships are found from the data, not hard coded:

* `transactions.CustomerID -> customers.CustomerID` (foreign key, 100% match)
* `transactions.MerchantID -> merchants.MerchantID` (foreign key, 100% match)
* `transactions.TimeID -> time.TimeID` (foreign key, 100% match)
* `transactions.LocationID <-> customers.HomeLocationID` (shared location domain, becomes `dim_location`)

How it works: a column is a candidate key when it is (almost) complete and unique. A column in another table is a foreign key when at least 90% of its values exist in that key. ID columns that share a prefix (such as `L` for location) but have no owning table are treated as a shared domain. The table with the most foreign keys is chosen as the fact table.

---

## 5. Data cleaning and validation

Every check is logged, even when it finds nothing, and unrepairable rows are quarantined with a reason in `data/processed/rejected_records.csv`.

| Check | Action |
| --- | --- |
| Whitespace and null tokens ("NA", "null", "-", blank) | trimmed or set to null |
| Exact duplicate rows | removed, first copy kept |
| Duplicate primary keys | quarantined |
| Null required columns (null CustomerID, TransactionID, TimeID, Amount, Date, Hour) | quarantined |
| ID format (C001, T1001, M001, L001) | required IDs quarantined, optional IDs set to Unknown |
| Amount type ("INR 1,200.50" is repaired, "abc" is rejected) | parsed or quarantined |
| Amount zero, negative or above 10,000,000 | quarantined |
| Date conversion | parsed, unparseable dates quarantined |
| Hour outside 0 to 23 | quarantined |
| DayOfWeek, Month, Year consistency | re-derived from the date |
| Channel and segment values ("online", "mobile", "atm") | mapped to Digital, Branch, ATM, else Unknown |
| Missing category, merchant, location, name | filled with an explicit label |
| Transaction with unknown CustomerID or TimeID | quarantined (referential integrity) |
| Merchant master: missing name, category or risk rating | filled with an explicit label; an invalid risk rating becomes Unknown and is treated as risky |
| Transaction with a MerchantID not in the merchant master | kept (the payment happened), merchant added as "Unregistered merchant" and alerted by rule R08 |

Reports: `reports/cleaning_report.md` and `reports/cleaning_report.json`. The checks are also stored in the `data_quality_log` table and shown on the Data Quality page.

The supplied sample files are clean, so every check passes. The same code was tested on a deliberately corrupted copy of the files and correctly caught all planted issues.

---

## 6. Feature engineering

All history features look only backwards in time for each customer, so a transaction never uses information from its own future.

| Group | Features |
| --- | --- |
| Time | txn_datetime, txn_hour, day_of_week, month, year_month, is_weekend, time_bucket (Night, Morning, Afternoon, Evening) |
| Amount and category | amount_band, category_value_share |
| Customer history | customer_txn_seq, prior_txn_count, prior_avg_amount, hours_since_prev_txn, prev_location, prev_channel |
| Merchant | merchant_frequency, merchant_unique_customers, customer_merchant_visit_no, is_repeat_merchant, is_new_category |
| Merchant master | MerchantName, MerchantCategory, MerchantRiskLevel, is_registered_merchant, is_high_risk_merchant, is_category_mismatch (booked category differs from the merchant's registered category) |
| Geo | is_home_location, location_frequency, is_new_location, location_changed |
| Channel | channel_group (Digital or Physical), is_digital, is_preferred_channel, channel_changed |
| Customer profile | total_spend, avg_spend, median_spend, max_spend, txn_count, preferred channel (observed), preferred location, favourite category, distinct merchants and locations, digital share, geo consistency index |

---

## 7. Database design (SQLite)

Star schema in `data/output/customer_analytics.db`, defined in `src/database/sql/schema.sql`.

| Table | Grain | Notes |
| --- | --- | --- |
| fact_transaction | one row per transaction | amount and all engineered features, FKs to every dimension |
| dim_customer | one row per customer | master data plus behaviour profile |
| dim_time | one row per time slot | calendar and hour |
| dim_merchant | one row per merchant | merchant master (name, category, risk rating) plus activity and category match ratio; unregistered merchants seen in transactions are added with is_registered = 0 |
| dim_location | one row per location | derived shared domain |
| anomaly_rule | one row per rule | rule catalogue with severity |
| anomaly_alert | one row per rule hit | reason text for analysts |
| transaction_risk | one row per transaction | risk score and level |
| pipeline_run | one row per run | run metadata |
| data_quality_log | one row per check per run | cleaning audit trail |

Views (`views.sql`): `vw_transaction_details`, `vw_alert_details`, `vw_customer_360`.

Integrity: primary keys, foreign keys (enforced with `PRAGMA foreign_keys = ON` and checked after load), CHECK constraints on amount, hour, segment, channel and risk level, and indexes on the common filter columns.

Example queries you can run in any SQLite client:

```sql
-- Digital vs branch mix by segment
SELECT segment, channel, COUNT(*) AS txns
FROM vw_transaction_details
GROUP BY segment, channel;

-- Highest risk transactions with the reason
SELECT transaction_id, customer_name, rule_name, severity, details
FROM vw_alert_details
ORDER BY risk_score DESC
LIMIT 10;
```

---

## 8. KPI engine

All KPIs are SQL queries in `src/database/sql/kpi_queries.sql`. Each query reads from `ft` (filtered transactions). At run time the engine adds:

```sql
WITH ft AS (SELECT * FROM vw_transaction_details WHERE <filters>)
```

The batch pipeline uses no filters and the dashboard passes the sidebar filters as SQL parameters. One SQL file serves both, so the reports and the dashboard always agree, and user input is never pasted into SQL text.

| KPI | Definition |
| --- | --- |
| Customer segmentation | Business segment metrics (customers, value, average spend, frequency, digital share) plus value tiers that split customers into three equal groups by spend using `NTILE(3)`, and engagement tiers by frequency |
| Peak transaction time | Transactions and value by hour, part of day, weekday, and a weekday by hour heatmap |
| Repeat merchant ratio | (transactions minus unique customer and merchant pairs) divided by transactions |
| Geo-location consistency index | For each customer with 2+ transactions, the share of transactions at their most used location, averaged across customers (1.0 means always the same place). Home location ratio is reported alongside |
| Digital vs branch mix | Channel share of count and value, digital to branch ratio, digital share of digital plus branch, by segment and by month, and preferred vs actual channel |
| Merchant risk exposure | Transactions, value and customers by the merchant's risk rating, plus share of transactions at High risk merchants |
| Merchant category consistency | How often the category booked on a transaction matches the merchant's registered category, by merchant category |

### Sample results on the supplied data

| KPI | Value |
| --- | --- |
| Transactions | 100 |
| Active customers | 47 of 60 |
| Total value | 237,739.48 |
| Average transaction value | 2,377.39 |
| Digital share | 32.0% |
| Digital to branch ratio | 0.86 |
| Repeat merchant ratio | 3.0% |
| Transactions at High risk merchants | 4.0% (2 merchants, 4 customers) |
| Category mismatch | 81.0% of transactions |
| Geo-location consistency index | 0.40 |
| Busiest hour / part of day / weekday | 08:00 / Morning / Friday |

Full detail: `reports/kpi_report.md` and `data/output/kpi_*.csv`.

---

## 9. Rule-based anomaly detection

Nine explainable business rules, no machine learning. Thresholds live in `src/utils/config.py`.

| Code | Rule | Fires when | Severity |
| --- | --- | --- | --- |
| R01_HIGH_VALUE | High value transaction | amount at or above the 95th percentile | High |
| R02_ODD_HOUR | Unusual transaction time | between 00:00 and 04:59 | Medium |
| R03_LOCATION_JUMP | Sudden location change | new non home location within 168 hours of a transaction elsewhere | High |
| R04_MERCHANT_CHANGE | Sudden merchant change | customer with 2+ earlier transactions uses a new merchant in a category they never used | Medium |
| R05_BEHAVIOUR_CHANGE | Spending behaviour change | amount at least 2x or at most 0.25x the customer's running average (2+ earlier transactions) | Medium |
| R06_DIGITAL_TO_BRANCH | Digital to branch shift | digital first customer transacts at a branch | Medium |
| R07_CHANNEL_CHANGE | Channel change | channel switched from the previous transaction to a non preferred one | Low |
| R08_HIGH_RISK_MERCHANT | High risk merchant | merchant rated High in the merchant master, or not in the master at all | High |
| R09_CATEGORY_MISMATCH | Category mismatch at risky merchant | booked category differs from the registered category of a Medium or High risk merchant | Medium |

Category mismatches at Low risk merchants are not alerted. In the sample data 81% of transactions carry a different category from the merchant's registration, so alerting on all of them would bury the real signals. They are tracked as a KPI instead.

**Risk scoring.** Severity weights (Low 1, Medium 2, High 3) are added per transaction. Score 5+ is High risk, 3 to 4 is Medium, 1 to 2 is Low, and 0 is None.

**Sample results:** 124 alerts on 71 transactions, with 20 high risk and 18 medium risk transactions. The sample data is randomly generated, so channel and time rules fire more often than they would on real bank data. Most of those land in the Low tier, and the dashboard alert queue shows High and Medium by default.

Outputs: `anomaly_alert` and `transaction_risk` tables, `data/output/anomaly_alerts.csv`, and `reports/anomaly_report.md`.

---

## 10. Dashboard

| Page | Contents |
| --- | --- |
| Project Home | Architecture diagram, latest run status, data model row counts, detected relationships |
| KPI Dashboard | Eight KPI cards and tabs for segmentation, peak time, merchants (repeat ratio, merchant risk exposure, category consistency), geo consistency, digital vs branch and categories |
| Customer Search | Search by ID or name, profile, KPI cards, transaction timeline sized by risk, category split, history and alerts |
| Anomaly Alerts | Alert and risk cards, alerts by rule, risk distribution, filterable alert queue with reasons, CSV download, riskiest customers, rule catalogue |
| Data Quality | Schema validation per file, every cleaning check, quarantined records |

Sidebar filters (date range, segment, channel, category, merchant risk rating, transaction risk level) apply to the KPI and alert pages and are passed straight into the SQL queries.

---

## 11. Generated outputs

| Location | File | Content |
| --- | --- | --- |
| data/processed | clean_customers.csv, clean_merchants.csv, clean_time.csv, clean_transactions.csv | cleaned source tables |
| data/processed | transaction_features.csv, customer_features.csv | engineered features |
| data/processed | rejected_records.csv | quarantined rows with reasons |
| data/output | customer_analytics.db | SQLite database |
| data/output | kpi_*.csv | one file per KPI query |
| data/output | anomaly_alerts.csv, transaction_risk.csv | alerts and risk scores |
| reports | pipeline_summary.md / .json | schema validation, relationships, timings, row counts |
| reports | cleaning_report.md / .json | data quality audit |
| reports | kpi_report.md | KPI summary |
| reports | anomaly_report.md | alert summary |
| reports | pipeline_run.log | full run log |
| reports/dashboard_screenshots | 01 to 05 *.png | sample screenshots of the dashboard pages |

---

## 12. Configuration

Everything tunable is in `src/utils/config.py`:

* folder and database paths
* valid channels, segments and channel synonyms
* time buckets and amount bands
* anomaly thresholds (percentile, odd hour window, location window, behaviour multipliers)
* severity weights and risk level bands

Change a value and run `python main.py` again.

---

## 13. Design decisions worth explaining in an interview

* **Read everything as text first.** Pandas does not silently turn "1,200" into NaN. The cleaning stage decides, logs and quarantines.
* **Quarantine, do not drop.** Every rejected row keeps its original values and a reason, which is what auditors expect.
* **Relationships from data, not names.** New or renamed files still load correctly.
* **Dimensions cleaned before facts.** Referential integrity is checked against cleaned keys.
* **Unknown merchants are kept, unknown customers are not.** A payment to a merchant missing from the master still happened, so it is kept and alerted. A transaction without a valid customer cannot be attributed to anyone, so it is quarantined.
* **Two risk levels, kept apart.** The merchant's rating comes from master data (`merchant_risk_level`); the transaction's risk level comes from the rules (`risk_level`). The source column `RiskLevel` is renamed early so the two never get mixed up.
* **No look ahead in features.** Running averages and previous values only use earlier transactions, so rules behave the same in batch and in a future real time version.
* **One SQL file for reports and dashboard.** The filtered CTE pattern keeps numbers consistent and queries parameterised.
* **Rules over models.** Each alert has a one sentence reason that a fraud analyst can act on, and thresholds are business settings rather than model weights.
* **Idempotent full refresh.** `schema.sql` drops and recreates everything, so a run can be repeated safely.

---

## 14. Troubleshooting

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'src'` | Run commands from the project root folder |
| Dashboard says the database was not found | Run `python main.py` first |
| `streamlit` is not recognised | Activate the virtual environment, or use `python -m streamlit run src/dashboard/app.py` |
| PowerShell will not activate the venv | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Dashboard shows old numbers | Re-run `python main.py`; the dashboard cache refreshes when the database file changes |
