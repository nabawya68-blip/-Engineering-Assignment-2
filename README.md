# Data Cleaning

## Overview
Five files were uploaded (the data part of Assignment 2):

| File | Rows | What it is |
|---|---|---|
| `customers_master.csv` | 150 | customers |
| `products_master.csv` | 30 | products |
| `orders.csv` | 1,020 | order lines for October 2025 |
| `new_daily_batch.csv` | 333 | order lines for 1-7 Nov 2025, same schema as orders |
| `previous_days_summary.csv` | 30 | daily quality summary for September 2025 |

Each order can have several lines (one per product), so a repeated `Order_ID`
is **not** a duplicate — only completely identical rows are.

## Problems found and how they were solved
1. **Inconsistent spelling / case / spaces in text columns**
   `Region` had 13 raw spellings (`mansoura`, ` Cairo`, `CAIRO`, `Alexandria `...)
   for only 4 real regions. Same for product `Category` (8 spellings → 5),
   `Order_Status` (` delivered `, `SHIPPED`) and `Payment_Method`
   (`wallet`, `CARD`, ` Card`, `ONLINE`...).
   → stripped whitespace and used Title Case everywhere.
2. **Exact duplicate rows** — 2 in orders, 4 in the daily batch → dropped.
3. **Missing Customer_ID (3 in orders, 4 in the batch) and one invalid
   Order_Date (`not-a-date`)** — all lines of one order share the customer
   and the order date, so these were recovered from the other lines of the
   same `Order_ID`. Only 1 batch row (`NB000088`) could not be recovered.
4. **Mixed formats in the daily batch** — `Quantity` came as `4 pcs`,
   `Discount` as `15%`. → extracted the number from Quantity and converted
   percentages to fractions (15% → 0.15), so the batch matches orders.
5. **Missing Shipping_Cost (9 rows in the batch)** → filled with the median
   shipping cost (35).
6. **Invalid values that cannot be fixed** — these rows were moved to
   `rejected/` with a `rejection_reason` instead of being silently deleted:
   - quantity ≤ 0 (orders: 2, batch: 2)
   - discount outside [0, 1], e.g. 1.2, 1.3, −0.1 (orders: 2, batch: 3)
   - unit price `unknown` / missing (orders: 2)
   - Product_ID not in products_master: `PX01`, `PX02`, `P555`, `P666` (orders: 2, batch: 4)
   - Customer_ID not in customers_master: `C5555`, `C6666`, plus the one unrecoverable missing customer (batch: 5)
   - Ship_Date before Order_Date (orders: 1, batch: 4)
7. **Missing Ship_Date** — for Pending/Cancelled orders this is normal
   (not shipped yet), so it was left empty.
   *Remaining warning:* 10 Delivered rows in the cleaned batch still have
   no Ship_Date. There is no correct value to fill in, so the date was left
   empty rather than inventing one.
8. **`previous_days_summary.csv` needed no cleaning** — no missing values,
   no duplicates, dates are consecutive (1-30 Sep 2025) and all rates are
   within [0, 1]. Only the types/formats were checked and standardised.

## Results
| File | Before | Clean | Duplicates removed | Rejected |
|---|---|---|---|---|
| customers_master | 150 | 150 | 0 | 0 |
| products_master | 30 | 30 | 0 | 0 |
| orders | 1,020 | **1,009** | 2 | 9 |
| new_daily_batch | 333 | **311** | 4 | 18 |
| previous_days_summary | 30 | 30 | 0 | 0 |

`cleaned/all_orders_clean.csv` (1,320 rows) combines the cleaned orders and
the cleaned daily batch, ready to be used for the indexes & views part.

## Files
- `clean_data.ipynb` / `clean_data.py` — the cleaning code
- `cleaned/` — the cleaned CSV files
- `rejected/` — the rejected rows, each with its `rejection_reason`

## How to run
```bash
pip install pandas
python clean_data.py
```
