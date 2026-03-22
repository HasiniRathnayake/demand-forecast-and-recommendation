"""
upload.py — Write ML predictions back to Supabase
Project: 2026-Y2-S2-KU-AI-02
"""

import requests
import json
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from config import SUPABASE_URL, HEADERS, TABLE_REPLENISHMENT, LEAD_TIME_DAYS, COVERAGE_TARGET


def _generate_reasoning(row: dict, forecasts: dict) -> str:
    """Build a human-readable ML reasoning string for the dashboard."""
    code    = row["product_code"]
    segment = row.get("demand_segment", "Unknown")
    urgency = row.get("urgency_tier", "LOW")
    vel     = round(float(row.get("avg_daily_qty_norm", 0)), 2)
    stock   = int(row.get("net_stock", 0))
    eff     = int(row.get("effective_stock", 0))
    rp      = int(row.get("reorder_point", 0))
    opt     = int(row.get("optimal_level", 0))
    qty     = int(row.get("ml_suggested_qty", 0))
    f30     = round(float(forecasts.get(code, vel * 30)), 1)

    method  = "Prophet time-series forecast" if code in forecasts and f30 != vel * 30 else "ML linear extrapolation"

    return (
        f"[ML PREDICTION] SKU classified as {segment} (K-Means cluster). "
        f"Urgency tier: {urgency} — stock coverage is {round(eff / vel, 1) if vel > 0 else '∞'} days. "
        f"Daily velocity: {vel} units/day | 30-day demand forecast ({method}): {f30} units. "
        f"Effective stock (incl. pending POs): {eff} units vs. reorder point of {rp} units. "
        f"XGBoost model recommends ordering {qty} units to restore to optimal level of {opt} units "
        f"+ {int(0.10*100)}% safety buffer."
    )


def build_records(df: pd.DataFrame, forecasts: dict) -> list[dict]:
    """Convert ML prediction dataframe to Supabase-ready records."""
    now = datetime.now(timezone.utc).isoformat()
    records = []

    # Only include products that need reordering
    reorder_df = df[df["ml_suggested_qty"] > 0].copy()
    reorder_df = reorder_df.sort_values("stock_coverage_days", ascending=True)

    for idx, (_, row) in enumerate(reorder_df.iterrows()):
        vel = float(row.get("avg_daily_qty_norm", 0))
        f30 = float(forecasts.get(row["product_code"], vel * 30))

        records.append({
            "order_id":                  f"ML-2026-{str(idx+1).zfill(4)}",
            "generated_at":              now,
            "product_code":              str(row["product_code"]),
            "product_name":              str(row.get("product_name", "UNKNOWN PRODUCT")),
            "current_stock_level":       int(row.get("net_stock", 0)),
            "reorder_point":             int(row.get("reorder_point", 0)),
            "optimal_level":             int(row.get("optimal_level", 0)),
            "pending_po_qty":            int(row.get("pending_po_qty", 0)),
            "effective_stock":           int(row.get("effective_stock", 0)),
            "suggested_qty":             int(row.get("ml_suggested_qty", 0)),
            "estimated_order_value_kwd": float(row.get("estimated_order_value_kwd", 0)),
            "daily_sales_velocity":      round(vel, 4),
            "forecast_7day_demand":      round(vel * 7, 1),
            "status":                    "PENDING_APPROVAL",
            "reasoning":                 _generate_reasoning(dict(row), forecasts),
        })

    return records


def clear_existing_records():
    """Delete all existing rows in replenishment_orders before re-inserting."""
    print(f"\n🗑️  Clearing existing records from {TABLE_REPLENISHMENT}...")
    # Supabase REST: DELETE with no filter requires neq trick
    url  = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?order_id=neq.NONEXISTENT"
    resp = requests.delete(url, headers={**HEADERS, "Prefer": "return=minimal"})
    if resp.status_code in (200, 204):
        print("   ✅ Cleared.")
    else:
        print(f"   ⚠️  Clear returned {resp.status_code}: {resp.text[:200]}")


def upload_records(records: list[dict], batch_size: int = 200, dry_run: bool = False):
    """Batch insert records into Supabase replenishment_orders table."""
    if dry_run:
        print(f"\n🔍 DRY RUN — would upload {len(records)} records:")
        for r in records[:5]:
            print(f"   {r['order_id']} | {r['product_code']} | qty={r['suggested_qty']} | {r['reasoning'][:80]}…")
        return

    inserted = 0
    failed   = 0

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        url   = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}"
        resp  = requests.post(
            url,
            headers = {**HEADERS, "Prefer": "return=minimal"},
            json    = batch,
        )
        if resp.status_code in (200, 201):
            inserted += len(batch)
            print(f"   Batch {i//batch_size+1}: ✅ inserted {len(batch)} rows")
        else:
            failed += len(batch)
            print(f"   Batch {i//batch_size+1}: ❌ {resp.status_code} — {resp.text[:200]}")

    print(f"\n📤 Upload complete: {inserted} inserted, {failed} failed.")
