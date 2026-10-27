# Pipeline Run Summary

Run ID: `RUN_20261027_070912_8e6f79`  
Started: 2026-10-27 07:09:12  
Finished: 2026-10-27 07:09:13  
Duration: 0.639 s  
Status: SUCCESS

## Schema validation

| table | file | rows | columns | missing_columns | extra_columns | type_issues | pattern_issues | is_valid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| customers | Customers.csv | 60 | 5 | [] | [] | {} | {} | True |
| merchants | Merchants.csv | 60 | 4 | [] | [] | {} | {} | True |
| time | Time.csv | 60 | 6 | [] | [] | {} | {} | True |
| transactions | Transactions.csv | 100 | 8 | [] | [] | {} | {} | True |

## Detected relationships

- transactions.CustomerID -> customers.CustomerID [foreign_key, match=100%]
- transactions.MerchantID -> merchants.MerchantID [foreign_key, match=100%]
- transactions.TimeID -> time.TimeID [foreign_key, match=100%]
- transactions.LocationID <-> customers.HomeLocationID [shared_domain, match=56%]

## Stage timings (seconds)

| ingestion | cleaning | merge | features | anomaly | database | kpi |
| --- | --- | --- | --- | --- | --- | --- |
| 0.068 | 0.115 | 0.017 | 0.172 | 0.073 | 0.108 | 0.085 |

## SQLite table row counts

| table | rows |
| --- | --- |
| anomaly_alert | 124 |
| anomaly_rule | 9 |
| data_quality_log | 0 |
| dim_customer | 60 |
| dim_location | 55 |
| dim_merchant | 60 |
| dim_time | 60 |
| fact_transaction | 100 |
| pipeline_run | 0 |
| transaction_risk | 100 |

Database file: `data/output/customer_analytics.db`