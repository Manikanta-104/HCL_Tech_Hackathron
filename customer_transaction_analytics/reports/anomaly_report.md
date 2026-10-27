# Anomaly Detection Report

Rule based detection only. Each alert carries the business reason that triggered it.

Total alerts: 124 on 71 transactions.

## Alerts by rule

| rule_code | rule_name | severity | alerts | customers_affected | value_at_risk |
| --- | --- | --- | --- | --- | --- |
| R02_ODD_HOUR | Unusual transaction time | Medium | 25 | 21 | 59,767.59 |
| R06_DIGITAL_TO_BRANCH | Digital to branch shift | Medium | 20 | 14 | 53,984.71 |
| R09_CATEGORY_MISMATCH | Category mismatch at risky merchant | Medium | 19 | 16 | 31,291.61 |
| R07_CHANNEL_CHANGE | Channel change | Low | 16 | 14 | 29,861.94 |
| R03_LOCATION_JUMP | Sudden location change | High | 14 | 12 | 35,597.86 |
| R04_MERCHANT_CHANGE | Sudden merchant change | Medium | 14 | 10 | 34,934.94 |
| R05_BEHAVIOUR_CHANGE | Spending behaviour change | Medium | 7 | 5 | 14,143.22 |
| R01_HIGH_VALUE | High value transaction | High | 5 | 5 | 24,221.50 |
| R08_HIGH_RISK_MERCHANT | High risk merchant | High | 4 | 4 | 8,949.14 |

## Risk level distribution

| risk_level | transactions | total_value |
| --- | --- | --- |
| High | 20 | 47,706.66 |
| Medium | 18 | 47,150.16 |
| Low | 33 | 74,058.67 |
| None | 29 | 68,823.99 |

## Customers with the highest risk

| customer_id | customer_name | segment | transactions | alerts | total_risk_score | max_risk_score | high_risk_txns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C060 | Maria Taylor | Student | 5 | 12 | 26 | 12 | 2 |
| C003 | Brittney Gallagher | Standard | 5 | 10 | 21 | 9 | 2 |
| C056 | Sherry Chapman | Standard | 6 | 8 | 17 | 5 | 1 |
| C057 | Patrick Phillips | Premium | 3 | 7 | 15 | 6 | 2 |
| C048 | Ronnie Mcgee | Standard | 4 | 7 | 13 | 7 | 2 |
| C052 | Joyce Wilson | Standard | 4 | 6 | 13 | 7 | 2 |
| C051 | George Watkins | Standard | 4 | 7 | 13 | 6 | 1 |
| C058 | Erik Rios | Premium | 3 | 6 | 12 | 7 | 1 |
| C010 | Michele Diaz | Student | 3 | 4 | 10 | 7 | 1 |
| C024 | Andrew Cook | Premium | 2 | 4 | 10 | 7 | 1 |

## Highest priority alerts

| alert_id | txn_datetime | transaction_id | customer_id | rule_name | severity | amount | risk_level | details |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A00015 | 2026-01-12 02:00:00 | T070 | C060 | High value transaction | High | 4,935.09 | High | Amount 4,935.09 is at or above the P95 threshold of 4,747.43 |
| A00016 | 2026-01-12 02:00:00 | T070 | C060 | Sudden location change | High | 4,935.09 | High | Moved from L002 to L058 within 32 h (home is L033) |
| A00017 | 2026-01-12 02:00:00 | T070 | C060 | Unusual transaction time | Medium | 4,935.09 | High | Transaction at 02:00, inside the unusual window 00:00 to 04:59 |
| A00018 | 2026-01-12 02:00:00 | T070 | C060 | Sudden merchant change | Medium | 4,935.09 | High | First ever Travel spend, at new merchant M047, after 2 earlier transactions |
| A00019 | 2026-01-12 02:00:00 | T070 | C060 | Spending behaviour change | Medium | 4,935.09 | High | Spent 4,935.09, which is 4.8x the customer's average of 1,022.94 |
| A00061 | 2026-02-08 03:00:00 | T088 | C003 | Sudden location change | High | 3,205.91 | High | Moved from L058 to L022 within 19 h (home is L048) |
| A00062 | 2026-02-08 03:00:00 | T088 | C003 | Unusual transaction time | Medium | 3,205.91 | High | Transaction at 03:00, inside the unusual window 00:00 to 04:59 |
| A00063 | 2026-02-08 03:00:00 | T088 | C003 | Sudden merchant change | Medium | 3,205.91 | High | First ever Healthcare spend, at new merchant M048, after 3 earlier transactions |
| A00064 | 2026-02-08 03:00:00 | T088 | C003 | Category mismatch at risky merchant | Medium | 3,205.91 | High | Booked as Healthcare at Thompson Ltd, which is registered as Retail (Medium risk merchant) |
| A00049 | 2026-02-03 09:00:00 | T073 | C060 | Sudden merchant change | Medium | 77.33 | High | First ever Utilities spend, at new merchant M033, after 3 earlier transactions |
| A00050 | 2026-02-03 09:00:00 | T073 | C060 | Spending behaviour change | Medium | 77.33 | High | Spent 77.33, which is 0.0x the customer's average of 2,326.99 |
| A00051 | 2026-02-03 09:00:00 | T073 | C060 | Digital to branch shift | Medium | 77.33 | High | Customer prefers Digital but transacted at a Branch |
| A00052 | 2026-02-03 09:00:00 | T073 | C060 | Category mismatch at risky merchant | Medium | 77.33 | High | Booked as Utilities at Miller PLC, which is registered as Retail (Medium risk merchant) |
| A00107 | 2026-02-25 08:00:00 | T063 | C052 | Sudden location change | High | 4,152.25 | High | Moved from L058 to L031 within 17 h (home is L001) |
| A00077 | 2026-02-12 04:00:00 | T023 | C010 | High risk merchant | High | 1,496.12 | High | Paid 1,496.12 to Blake-Miller (M057), rated High risk |
| A00068 | 2026-02-09 03:00:00 | T041 | C058 | Sudden location change | High | 654.09 | High | Moved from L029 to L005 within 154 h (home is L049) |
| A00007 | 2026-01-06 02:00:00 | T027 | C024 | High risk merchant | High | 1,038.39 | High | Paid 1,038.39 to Shaw Ltd (M017), rated High risk |
| A00108 | 2026-02-25 08:00:00 | T063 | C052 | Sudden merchant change | Medium | 4,152.25 | High | First ever Retail spend, at new merchant M059, after 3 earlier transactions |
| A00109 | 2026-02-25 08:00:00 | T063 | C052 | Category mismatch at risky merchant | Medium | 4,152.25 | High | Booked as Retail at Hanson-Thompson, which is registered as Healthcare (Medium risk merchant) |
| A00078 | 2026-02-12 04:00:00 | T023 | C010 | Unusual transaction time | Medium | 1,496.12 | High | Transaction at 04:00, inside the unusual window 00:00 to 04:59 |
| A00079 | 2026-02-12 04:00:00 | T023 | C010 | Digital to branch shift | Medium | 1,496.12 | High | Customer prefers Digital but transacted at a Branch |
| A00069 | 2026-02-09 03:00:00 | T041 | C058 | Unusual transaction time | Medium | 654.09 | High | Transaction at 03:00, inside the unusual window 00:00 to 04:59 |
| A00070 | 2026-02-09 03:00:00 | T041 | C058 | Sudden merchant change | Medium | 654.09 | High | First ever Utilities spend, at new merchant M058, after 2 earlier transactions |
| A00029 | 2026-01-26 22:00:00 | T055 | C048 | Sudden merchant change | Medium | 3,009.60 | High | First ever Utilities spend, at new merchant M048, after 2 earlier transactions |
| A00030 | 2026-01-26 22:00:00 | T055 | C048 | Spending behaviour change | Medium | 3,009.60 | High | Spent 3,009.60, which is 10.5x the customer's average of 285.46 |

_Showing 25 of 124 rows._
