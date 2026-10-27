# KPI Report

Period covered: 2026-01-01 to 2026-02-28

## Headline numbers

| KPI | Value |
| --- | --- |
| Transactions | 100 |
| Active customers | 47 |
| Active merchants | 48 |
| Total value | 237,739.48 |
| Average transaction value | 2,377.39 |
| Digital share of transactions | 32.00% |
| Repeat merchant ratio | 3.00% |
| Geo-location consistency index | 0.3952 |
| Digital to branch ratio | 0.86 |
| Share of transactions at High risk merchants | 4.00% |
| Transactions with a category mismatch | 81.00% |
| Flagged transactions | 71 |
| High risk transactions | 20 |

## 1. Customer segmentation

| segment | customers | transactions | total_value | avg_txn_value | avg_spend_per_customer | txns_per_customer | value_share_pct | digital_share_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Standard | 18 | 42 | 98,055.00 | 2,334.64 | 5,447.50 | 2.33 | 41.24 | 33.33 |
| Student | 14 | 33 | 74,268.66 | 2,250.57 | 5,304.90 | 2.36 | 31.24 | 39.39 |
| Premium | 15 | 25 | 65,415.82 | 2,616.63 | 4,361.05 | 1.67 | 27.52 | 20.00 |

Value tiers (NTILE on total spend) by segment:

| value_tier | segment | customers | total_spend |
| --- | --- | --- | --- |
| High Value | Premium | 3 | 25,173.32 |
| High Value | Standard | 6 | 61,296.93 |
| High Value | Student | 7 | 53,608.56 |
| Mid Value | Premium | 7 | 32,205.86 |
| Mid Value | Standard | 6 | 24,063.40 |
| Mid Value | Student | 3 | 12,842.65 |
| Low Value | Premium | 5 | 8,036.64 |
| Low Value | Standard | 6 | 12,694.67 |
| Low Value | Student | 4 | 7,817.45 |

## 2. Peak transaction time

Busiest hour: 08:00 (10 transactions). Busiest part of day: Morning (06-11). Busiest weekday: Friday.

| time_bucket | transactions | total_value | txn_share_pct |
| --- | --- | --- | --- |
| Night (00-05) | 25 | 59,767.59 | 25.00 |
| Morning (06-11) | 30 | 71,064.76 | 30.00 |
| Afternoon (12-17) | 20 | 40,473.77 | 20.00 |
| Evening (18-23) | 25 | 66,433.36 | 25.00 |

| day_of_week | transactions | total_value | avg_value |
| --- | --- | --- | --- |
| Monday | 12 | 34,623.21 | 2,885.27 |
| Tuesday | 13 | 24,654.82 | 1,896.52 |
| Wednesday | 13 | 29,001.04 | 2,230.85 |
| Thursday | 18 | 36,366.32 | 2,020.35 |
| Friday | 21 | 49,576.85 | 2,360.80 |
| Saturday | 14 | 31,648.35 | 2,260.60 |
| Sunday | 9 | 31,868.89 | 3,540.99 |

## 3. Repeat merchant ratio

| transactions | unique_customer_merchant_pairs | repeat_transactions | repeat_merchant_ratio_pct | customers_with_repeat_merchant |
| --- | --- | --- | --- | --- |
| 100 | 97 | 3 | 3.00 | 3 |

| segment | transactions | repeat_transactions | repeat_merchant_ratio_pct |
| --- | --- | --- | --- |
| Standard | 42 | 2 | 4.76 |
| Student | 33 | 1 | 3.03 |
| Premium | 25 | 0 | 0.00 |

Top merchants:

| merchant_id | merchant_name | merchant_category | merchant_risk_level | transactions | unique_customers | repeat_visits | total_value | avg_value |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M043 | Sweeney-Hebert | Travel | Low | 6 | 5 | 1 | 10,780.45 | 1,796.74 |
| M020 | Lester Inc | Travel | Low | 4 | 3 | 1 | 11,102.39 | 2,775.60 |
| M028 | Yoder, Diaz and Barber | Retail | Low | 4 | 4 | 0 | 10,362.28 | 2,590.57 |
| M026 | Mcintyre, Perez and Weaver | Healthcare | Low | 4 | 4 | 0 | 5,024.86 | 1,256.22 |
| M013 | Miles Inc | Healthcare | Medium | 4 | 4 | 0 | 3,750.58 | 937.64 |
| M021 | Hunt, Anderson and Scott | Retail | Low | 3 | 3 | 0 | 11,434.02 | 3,811.34 |
| M048 | Thompson Ltd | Retail | Medium | 3 | 3 | 0 | 10,828.79 | 3,609.60 |
| M044 | Lopez, Hampton and Howard | Retail | Low | 3 | 3 | 0 | 9,918.07 | 3,306.02 |
| M047 | Estrada Inc | Retail | Low | 3 | 3 | 0 | 9,786.50 | 3,262.17 |
| M058 | Frederick Group | Travel | Low | 3 | 3 | 0 | 8,968.40 | 2,989.47 |

## 4. Geo-location consistency index

Average share of a customer's transactions made at their most used location (customers with two or more transactions).

| customers | customers_with_history | geo_consistency_index | home_location_ratio | avg_locations_per_customer |
| --- | --- | --- | --- | --- |
| 47 | 28 | 0.40 | 0.01 | 2.86 |

| segment | customers_with_history | geo_consistency_index | avg_locations_per_customer |
| --- | --- | --- | --- |
| Premium | 7 | 0.43 | 2.43 |
| Standard | 10 | 0.36 | 3.30 |
| Student | 11 | 0.40 | 2.73 |

## 5. Digital vs branch transaction mix

| channel | transactions | total_value | avg_value | txn_share_pct | value_share_pct |
| --- | --- | --- | --- | --- | --- |
| Branch | 37 | 93,258.86 | 2,520.51 | 37.00 | 39.23 |
| Digital | 32 | 64,546.53 | 2,017.08 | 32.00 | 27.15 |
| ATM | 31 | 79,934.09 | 2,578.52 | 31.00 | 33.62 |

| digital_txns | branch_txns | atm_txns | digital_to_branch_ratio | digital_share_of_digital_branch_pct | digital_share_pct | physical_share_pct |
| --- | --- | --- | --- | --- | --- | --- |
| 32 | 37 | 31 | 0.86 | 46.38 | 32.00 | 68.00 |

| segment | channel | transactions | share_within_segment_pct |
| --- | --- | --- | --- |
| Premium | ATM | 8 | 32.00 |
| Premium | Branch | 12 | 48.00 |
| Premium | Digital | 5 | 20.00 |
| Standard | ATM | 13 | 30.95 |
| Standard | Branch | 15 | 35.71 |
| Standard | Digital | 14 | 33.33 |
| Student | ATM | 10 | 30.30 |
| Student | Branch | 10 | 30.30 |
| Student | Digital | 13 | 39.39 |

## Merchant risk and category consistency

Activity by the merchant's risk rating in the merchant master:

| merchant_risk_level | merchants | customers | transactions | total_value | txn_share_pct | value_share_pct |
| --- | --- | --- | --- | --- | --- | --- |
| High | 2 | 4 | 4 | 8,949.14 | 4.00 | 3.76 |
| Medium | 10 | 18 | 22 | 39,829.39 | 22.00 | 16.75 |
| Low | 36 | 40 | 74 | 188,960.95 | 74.00 | 79.48 |

Registered merchant category against the category booked on the transaction:

| merchant_category | merchants | transactions | total_value | avg_value | category_match_pct | repeat_merchant_ratio_pct |
| --- | --- | --- | --- | --- | --- | --- |
| Travel | 16 | 34 | 89,521.14 | 2,632.97 | 11.76 | 5.88 |
| Retail | 14 | 33 | 80,360.41 | 2,435.16 | 30.30 | 3.03 |
| Healthcare | 15 | 29 | 59,753.71 | 2,060.47 | 13.79 | 0.00 |
| Utilities | 3 | 4 | 8,104.22 | 2,026.06 | 25.00 | 0.00 |

## Category spend

| category | transactions | total_value | avg_value | value_share_pct |
| --- | --- | --- | --- | --- |
| Utilities | 27 | 65,130.55 | 2,412.24 | 27.40 |
| Retail | 26 | 61,631.08 | 2,370.43 | 25.92 |
| Travel | 21 | 59,313.74 | 2,824.46 | 24.95 |
| Healthcare | 26 | 51,664.11 | 1,987.08 | 21.73 |
