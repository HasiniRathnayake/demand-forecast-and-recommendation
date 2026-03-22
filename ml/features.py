"""
features.py — Supabase data fetching & feature engineering
Project: 2026-Y2-S2-KU-AI-02
"""

import requests
import pandas as pd
import numpy as np
from config import SUPABASE_URL, HEADERS


# ── Low-level fetch ───────────────────────────────────────────────────────────

def fetch_table(table_name: str, limit: int = 10000) -> list[dict]:
    """Fetch all rows from a Supabase table using pagination."""
    PAGE = 1000
    all_rows = []
    offset = 0
    encoded = requests.utils.quote(table_name)

    while True:
        url = f"{SUPABASE_URL}/rest/v1/{encoded}?select=*&limit={PAGE}&offset={offset}"
        resp = requests.get(url, headers={**HEADERS, "Prefer": "count=exact"})
        resp.raise_for_status()
        rows = resp.json()
        all_rows.extend(rows)
        if len(rows) < PAGE:
            break
        offset += PAGE
        if offset >= limit:
            break

    return all_rows


# ── Feature engineering ───────────────────────────────────────────────────────

def build_feature_matrix() -> pd.DataFrame:
    """
    Pull raw data from Supabase and engineer features for ML models.

    Returns
    -------
    pd.DataFrame with one row per product_code and columns:
        product_code, product_name, cost_price,
        total_qty_sold, days_with_sales, avg_daily_qty, std_daily_qty,
        cv_demand, total_received, pending_po_qty, net_stock,
        stock_coverage_days, wastage_qty, total_revenue, avg_unit_price
    """
    print("📥 Fetching data from Supabase...")

    # --- Raw tables ---
    sales_rows    = fetch_table("His Sales")
    po_rows       = fetch_table("PO")
    item_rows     = fetch_table("Item Master")
    wastage_rows  = fetch_table("Wastage")

    print(f"   Sales rows:     {len(sales_rows)}")
    print(f"   PO rows:        {len(po_rows)}")
    print(f"   Item rows:      {len(item_rows)}")
    print(f"   Wastage rows:   {len(wastage_rows)}")

    # --- Item Master lookup ---
    item_df = pd.DataFrame(item_rows)
    item_lookup = {}
    if not item_df.empty and "Prod_Code" in item_df.columns:
        for _, r in item_df.iterrows():
            # Normalize key: uppercase + strip whitespace for reliable matching
            key = str(r["Prod_Code"]).strip().upper()
            item_lookup[key] = {
                "name":       str(r.get("Prod_Name", "UNKNOWN")).strip(),
                "cost_price": float(r.get("Prod_StadCostPrice", 0) or 0),
            }

    # --- Sales aggregation ---
    sales_df = pd.DataFrame(sales_rows)
    if sales_df.empty:
        raise ValueError("His Sales table is empty — cannot build features.")

    sales_df["Quantity"]   = pd.to_numeric(sales_df.get("Quantity", 0),   errors="coerce").fillna(0)
    sales_df["Unit_Price"] = pd.to_numeric(sales_df.get("Unit_Price", 0), errors="coerce").fillna(0)
    sales_df["Date"]       = sales_df["Date"].astype(str)

    # Parse YYYYMMDD date column
    sales_df["date_parsed"] = pd.to_datetime(sales_df["Date"], format="%Y%m%d", errors="coerce")
    sales_df = sales_df.dropna(subset=["date_parsed"])

    date_range_days = max(
        (sales_df["date_parsed"].max() - sales_df["date_parsed"].min()).days + 1, 1
    )
    print(f"   Sales date range: {sales_df['date_parsed'].min().date()} → {sales_df['date_parsed'].max().date()} ({date_range_days} days)")

    # Daily qty per product per day
    daily = (
        sales_df.groupby(["Product_Code", "date_parsed"])["Quantity"]
        .sum()
        .reset_index()
    )

    # Aggregate per product
    agg = daily.groupby("Product_Code").agg(
        total_qty_sold  = ("Quantity", "sum"),
        days_with_sales = ("date_parsed", "nunique"),
        avg_daily_qty   = ("Quantity", "mean"),
        std_daily_qty   = ("Quantity", "std"),
    ).reset_index()
    agg["std_daily_qty"] = agg["std_daily_qty"].fillna(0)
    agg["cv_demand"]     = np.where(
        agg["avg_daily_qty"] > 0,
        agg["std_daily_qty"] / agg["avg_daily_qty"],
        0
    )

    # Total revenue per product
    sales_df["revenue"] = sales_df["Quantity"] * sales_df["Unit_Price"]
    rev = sales_df.groupby("Product_Code").agg(
        total_revenue   = ("revenue", "sum"),
        avg_unit_price  = ("Unit_Price", "mean"),
    ).reset_index()

    agg = agg.merge(rev, on="Product_Code", how="left")
    agg["total_revenue"]  = agg["total_revenue"].fillna(0)
    agg["avg_unit_price"] = agg["avg_unit_price"].fillna(0)

    # Normalise sales velocity to per-day over the whole observed window
    agg["avg_daily_qty_norm"] = agg["total_qty_sold"] / date_range_days

    # --- PO aggregation ---
    po_df = pd.DataFrame(po_rows)
    if not po_df.empty:
        po_df["Quantity"]     = pd.to_numeric(po_df.get("Quantity", 0),     errors="coerce").fillna(0)
        po_df["Received_Qty"] = pd.to_numeric(po_df.get("Received_Qty", 0), errors="coerce").fillna(0)

        received = po_df.groupby("Prod_Code")["Received_Qty"].sum().reset_index()
        received.columns = ["Product_Code", "total_received"]

        pending = po_df[po_df["Received_Qty"] == 0].groupby("Prod_Code")["Quantity"].sum().reset_index()
        pending.columns = ["Product_Code", "pending_po_qty"]

        agg = agg.merge(received, on="Product_Code", how="left")
        agg = agg.merge(pending,  on="Product_Code", how="left")
    else:
        agg["total_received"] = 0
        agg["pending_po_qty"] = 0

    agg["total_received"] = agg["total_received"].fillna(0)
    agg["pending_po_qty"] = agg["pending_po_qty"].fillna(0)
    agg["net_stock"]      = np.maximum(0, agg["total_received"] - agg["total_qty_sold"])
    agg["effective_stock"] = agg["net_stock"] + agg["pending_po_qty"]

    # Stock coverage in days
    agg["stock_coverage_days"] = np.where(
        agg["avg_daily_qty_norm"] > 0,
        agg["effective_stock"] / agg["avg_daily_qty_norm"],
        999  # No velocity = unlimited coverage
    )

    # --- Wastage ---
    wastage_df = pd.DataFrame(wastage_rows)
    if not wastage_df.empty and "Prod_Code" in wastage_df.columns:
        wastage_df["Adj_Qty"] = pd.to_numeric(wastage_df.get("Adj_Qty", 0), errors="coerce").fillna(0)
        wastage_agg = wastage_df.groupby("Prod_Code")["Adj_Qty"].apply(
            lambda x: x.abs().sum()
        ).reset_index()
        wastage_agg.columns = ["Product_Code", "wastage_qty"]
        agg = agg.merge(wastage_agg, on="Product_Code", how="left")
    else:
        agg["wastage_qty"] = 0
    agg["wastage_qty"] = agg["wastage_qty"].fillna(0)

    # --- Join item lookup (normalize product code for matching) ---
    agg["product_name"] = agg["Product_Code"].map(
        lambda c: item_lookup.get(str(c).strip().upper(), {}).get("name", "UNKNOWN PRODUCT")
    )
    agg["cost_price"] = agg["Product_Code"].map(
        lambda c: item_lookup.get(str(c).strip().upper(), {}).get("cost_price", 0)
    )

    # Rename for clarity
    agg = agg.rename(columns={"Product_Code": "product_code"})

    print(f"\n✅ Feature matrix: {agg.shape[0]} products × {agg.shape[1]} features")
    return agg, date_range_days
