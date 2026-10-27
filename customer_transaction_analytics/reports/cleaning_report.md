# Data Cleaning Report

Generated: 2026-10-27 07:09:12

## Row counts per table

| table | rows_in | rows_out | rows_rejected |
| --- | --- | --- | --- |
| customers | 60 | 60 | 0 |
| merchants | 60 | 60 | 0 |
| time | 60 | 60 | 0 |
| transactions | 100 | 100 | 0 |

## Checks that found issues

All checks passed. The source data had no issues for these rules.

## Every check performed

| table | check | rows_affected | action |
| --- | --- | --- | --- |
| customers | Whitespace and null token standardisation | 0 | cells trimmed or set to null |
| customers | Exact duplicate rows | 0 | removed (first copy kept) |
| customers | Null check on required column CustomerID | 0 | quarantined |
| customers | ID format check on CustomerID | 0 | quarantined |
| customers | ID format check on HomeLocationID | 0 | set to null |
| customers | Duplicate primary key (CustomerID) | 0 | quarantined |
| customers | Missing CustomerName | 0 | filled with 'Unknown Customer' |
| customers | Missing Segment | 0 | filled with 'Unknown' |
| customers | Invalid Segment value | 0 | replaced with 'Unknown' |
| customers | Missing PreferredChannel | 0 | filled with 'Unknown' |
| customers | Invalid PreferredChannel value | 0 | replaced with 'Unknown' |
| customers | Missing HomeLocationID | 0 | filled with 'Unknown' |
| merchants | Whitespace and null token standardisation | 0 | cells trimmed or set to null |
| merchants | Exact duplicate rows | 0 | removed (first copy kept) |
| merchants | Null check on required column MerchantID | 0 | quarantined |
| merchants | ID format check on MerchantID | 0 | quarantined |
| merchants | Duplicate primary key (MerchantID) | 0 | quarantined |
| merchants | Missing MerchantName | 0 | filled with 'Unknown Merchant' |
| merchants | Missing MerchantCategory | 0 | filled with 'Uncategorized' |
| merchants | Missing merchant RiskLevel | 0 | filled with 'Unknown' |
| merchants | Invalid merchant RiskLevel value | 0 | replaced with 'Unknown' |
| time | Whitespace and null token standardisation | 0 | cells trimmed or set to null |
| time | Exact duplicate rows | 0 | removed (first copy kept) |
| time | Null check on required column TimeID | 0 | quarantined |
| time | Null check on required column Date | 0 | quarantined |
| time | Null check on required column HourOfDay | 0 | quarantined |
| time | ID format check on TimeID | 0 | quarantined |
| time | Duplicate primary key (TimeID) | 0 | quarantined |
| time | Date conversion | 0 | unparseable dates quarantined |
| time | HourOfDay range check (0-23) | 0 | quarantined |
| time | DayOfWeek consistency with Date | 0 | re-derived from Date |
| time | Month consistency with Date | 0 | re-derived from Date |
| time | Year consistency with Date | 0 | re-derived from Date |
| transactions | Whitespace and null token standardisation | 0 | cells trimmed or set to null |
| transactions | Exact duplicate rows | 0 | removed (first copy kept) |
| transactions | Null check on required column TransactionID | 0 | quarantined |
| transactions | Null check on required column CustomerID | 0 | quarantined |
| transactions | Null check on required column TimeID | 0 | quarantined |
| transactions | Null check on required column Amount | 0 | quarantined |
| transactions | ID format check on TransactionID | 0 | quarantined |
| transactions | ID format check on CustomerID | 0 | quarantined |
| transactions | ID format check on MerchantID | 0 | set to null |
| transactions | ID format check on TimeID | 0 | quarantined |
| transactions | ID format check on LocationID | 0 | set to null |
| transactions | Duplicate primary key (TransactionID) | 0 | quarantined |
| transactions | Amount data type check | 0 | quarantined |
| transactions | Amount must be positive | 0 | quarantined |
| transactions | Amount above 10,000,000 | 0 | quarantined |
| transactions | Missing Category | 0 | filled with 'Uncategorized' |
| transactions | Missing Channel | 0 | filled with 'Unknown' |
| transactions | Invalid Channel value | 0 | replaced with 'Unknown' |
| transactions | Missing MerchantID | 0 | filled with 'Unknown' |
| transactions | Missing LocationID | 0 | filled with 'Unknown' |
| transactions | Referential integrity: CustomerID | 0 | quarantined |
| transactions | Referential integrity: MerchantID | 0 | kept, merchant marked as unregistered |
| transactions | Referential integrity: TimeID | 0 | quarantined |

## Rejected (quarantined) records

Total rejected: 0. Full detail in `data/processed/rejected_records.csv`.

_No records were rejected._
