"""
Data cleaning - Assignment 2

Files:
  - customers_master.csv      (150 rows)
  - products_master.csv       (30 rows)
  - orders.csv                (1,020 order lines - one order can have several
                               lines, one per product, so Order_ID repeats
                               on purpose; only *exact* duplicate rows are
                               real duplicates)
  - new_daily_batch.csv       (333 order lines, same schema as orders)
  - previous_days_summary.csv (30 daily summary rows - already clean,
                               only type / format checks were needed)

Cleaning rules (same function is used for orders and the daily batch):
  1. Strip whitespace from every text field and standardise case
     (e.g. Region: 'mansoura', ' Cairo', 'CAIRO' -> 'Mansoura', 'Cairo';
      Order_Status: ' delivered ', 'SHIPPED' -> 'Delivered', 'Shipped';
      Payment_Method: 'wallet', 'CARD', ' Card' -> 'Wallet', 'Card').
  2. Drop exact duplicate rows.
  3. Parse dates; an invalid/missing Order_Date or a missing Customer_ID is
     recovered from the other lines of the same Order_ID when possible
     (all lines of one order share the customer and the order date).
  4. Quantity: extract the number ('4 pcs' -> 4) and convert to int.
     Discount: convert percentages ('15%' -> 0.15) to a fraction.
  5. Missing Shipping_Cost is filled with the median shipping cost.
  6. Rows that are still invalid are NOT silently deleted - they are saved
     to rejected/ with a `rejection_reason` column:
       - quantity <= 0
       - discount outside [0, 1]
       - unit price missing / not a number ('unknown')
       - Customer_ID missing or not found in customers_master
       - Product_ID not found in products_master
       - Ship_Date before Order_Date
  7. Known remaining warning (kept, documented in README): a few Delivered
     rows in the daily batch have no Ship_Date. There is no correct value
     to fill in, so the date is left empty instead of inventing one.

Outputs: cleaned/*.csv, rejected/*.csv and cleaned/all_orders_clean.csv
(orders + daily batch combined, ready for the indexes & views part).
"""

import re

import pandas as pd

# ---------------------------------------------------------------- masters
customers = pd.read_csv("customers_master.csv")
customers["Region"] = customers["Region"].str.strip().str.title()
customers["Customer_Segment"] = customers["Customer_Segment"].str.strip().str.title()
customers["Customer_Name"] = customers["Customer_Name"].str.strip()
customers = customers.drop_duplicates()
customers.to_csv("cleaned/customers_master_clean.csv", index=False)
print(f"customers: {len(customers)} rows, regions = {sorted(customers['Region'].unique())}")

products = pd.read_csv("products_master.csv")
products["Category"] = products["Category"].str.strip().str.title()
products["Product_Name"] = products["Product_Name"].str.strip()
products = products.drop_duplicates()
products.to_csv("cleaned/products_master_clean.csv", index=False)
print(f"products:  {len(products)} rows, categories = {sorted(products['Category'].unique())}")

valid_customers = set(customers["Customer_ID"])
valid_products = set(products["Product_ID"])


# ---------------------------------------------------------------- orders-like files
def clean_orders(df, name):
    start = len(df)

    # 1) text standardisation
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    df["Order_Status"] = df["Order_Status"].str.title()
    df["Payment_Method"] = df["Payment_Method"].str.title()

    # 2) exact duplicates
    df = df.drop_duplicates()
    duplicates_removed = start - len(df)

    # 3) types + value formats
    df["Order_Date"] = pd.to_datetime(df["Order_Date"], errors="coerce")
    df["Ship_Date"] = pd.to_datetime(df["Ship_Date"], errors="coerce")
    df["Quantity"] = pd.to_numeric(
        df["Quantity"].astype(str).str.extract(r"(-?\d+)")[0], errors="coerce"
    )
    df["Unit_Price"] = pd.to_numeric(df["Unit_Price"], errors="coerce")

    def parse_discount(value):
        if pd.isna(value):
            return pd.NA
        text = str(value).strip()
        if text.endswith("%"):
            return float(text[:-1]) / 100
        return float(text)

    df["Discount"] = df["Discount"].apply(parse_discount)

    # recover Customer_ID / Order_Date from the other lines of the same order
    df["Customer_ID"] = df.groupby("Order_ID")["Customer_ID"].transform(
        lambda s: s.ffill().bfill()
    )
    df["Order_Date"] = df.groupby("Order_ID")["Order_Date"].transform(
        lambda s: s.ffill().bfill()
    )

    # 5) shipping cost imputation
    df["Shipping_Cost"] = df["Shipping_Cost"].fillna(df["Shipping_Cost"].median())

    # 6) validation -> rejected rows keep a reason, nothing is lost silently
    def rejection_reason(row):
        if pd.isna(row["Quantity"]) or row["Quantity"] <= 0:
            return "quantity <= 0"
        if pd.isna(row["Discount"]) or not (0 <= row["Discount"] <= 1):
            return "discount outside [0, 1]"
        if pd.isna(row["Unit_Price"]):
            return "unit price missing / not a number"
        if pd.isna(row["Customer_ID"]) or row["Customer_ID"] not in valid_customers:
            return "customer not found in customers_master"
        if row["Product_ID"] not in valid_products:
            return "product not found in products_master"
        if pd.notna(row["Ship_Date"]) and pd.notna(row["Order_Date"]) and row["Ship_Date"] < row["Order_Date"]:
            return "ship date before order date"
        if pd.isna(row["Order_Date"]):
            return "order date missing / invalid"
        return None

    df["rejection_reason"] = df.apply(rejection_reason, axis=1)
    rejected = df[df["rejection_reason"].notna()].copy()
    clean = df[df["rejection_reason"].isna()].drop(columns="rejection_reason").copy()

    clean["Quantity"] = clean["Quantity"].astype(int)
    clean["Order_Date"] = clean["Order_Date"].dt.date
    clean["Ship_Date"] = clean["Ship_Date"].dt.date

    print(
        f"{name}: {start} rows -> {len(clean)} clean, "
        f"{duplicates_removed} exact duplicates removed, {len(rejected)} rejected"
    )
    print("  rejected by reason:")
    print(rejected["rejection_reason"].value_counts().to_string().replace("\n", "\n  "))
    return clean, rejected


orders_clean, orders_rejected = clean_orders(pd.read_csv("orders.csv"), "orders")
orders_clean.to_csv("cleaned/orders_clean.csv", index=False)
orders_rejected.to_csv("rejected/orders_rejected.csv", index=False)

batch_clean, batch_rejected = clean_orders(pd.read_csv("new_daily_batch.csv"), "new_daily_batch")
batch_clean.to_csv("cleaned/new_daily_batch_clean.csv", index=False)
batch_rejected.to_csv("rejected/new_daily_batch_rejected.csv", index=False)

all_orders = pd.concat([orders_clean, batch_clean], ignore_index=True)
all_orders.to_csv("cleaned/all_orders_clean.csv", index=False)
print(f"all_orders_clean: {len(all_orders)} rows")

# ---------------------------------------------------------------- summary
summary = pd.read_csv("previous_days_summary.csv")
summary["Date"] = pd.to_datetime(summary["Date"], errors="coerce").dt.date
summary = summary.sort_values("Date").drop_duplicates()
rate_cols = ["Valid_Records_Rate", "Missing_Rate", "Duplicate_Rate"]
assert summary[rate_cols].apply(lambda c: c.between(0, 1)).all().all(), "rate outside [0,1]"
assert summary.notna().all().all(), "summary still has missing values"
summary.to_csv("cleaned/previous_days_summary_clean.csv", index=False)
print(f"summary:   {len(summary)} rows, no missing values, all rates within [0, 1]")

print("\nDone. Cleaned files are in cleaned/, rejected rows (with reasons) in rejected/.")
