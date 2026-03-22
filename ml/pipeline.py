"""
pipeline.py — Main orchestrator for the Sunrise ML Procurement Pipeline
Project: 2026-Y2-S2-KU-AI-02

Usage:
    python pipeline.py            # Full run — train + predict + upload to Supabase
    python pipeline.py --dry-run  # Train + predict, print results, DO NOT upload
    python pipeline.py --skip-forecast  # Skip Prophet (faster, uses linear forecast)

This script replaces procurement_analysis.js entirely with a Python ML pipeline.
"""

import argparse
import sys
import time
import pandas as pd
import numpy as np

from features import build_feature_matrix, fetch_table
from models   import (
    train_kmeans, train_xgboost, train_random_forest, predict_all
)
from forecast import run_forecasts
from upload   import build_records, clear_existing_records, upload_records
from config   import LEAD_TIME_DAYS


def print_banner():
    print("=" * 60)
    print("  ☀️  SUNRISE SUPER PROCUREMENT ASSISTANT — ML PIPELINE")
    print("  Project: 2026-Y2-S2-KU-AI-02")
    print("=" * 60)


def print_summary(df: pd.DataFrame, records: list[dict]):
    """Print a human-readable summary after prediction."""
    print("\n" + "─" * 60)
    print("📊 PIPELINE SUMMARY")
    print("─" * 60)

    total = len(df)
    needs_reorder = len(df[df["ml_suggested_qty"] > 0])
    by_urgency = df[df["ml_suggested_qty"] > 0]["urgency_tier"].value_counts()
    by_segment = df["demand_segment"].value_counts()
    total_units = int(df["ml_suggested_qty"].sum())
    total_value = df["estimated_order_value_kwd"].sum()

    print(f"  Total SKUs analysed:          {total:,}")
    print(f"  SKUs flagged for reorder:     {needs_reorder:,}")
    print(f"  Total units to order:         {total_units:,}")
    print(f"  Estimated order value (KWD):  {total_value:,.2f}")
    print()
    print("  Demand Segments:")
    for seg, cnt in by_segment.items():
        print(f"    {seg:15s}: {cnt:,} SKUs")
    print()
    print("  Urgency Distribution:")
    for tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        cnt = by_urgency.get(tier, 0)
        print(f"    {tier:8s}: {cnt:,} products")
    print()
    print("  Top 10 Most Urgent Products:")
    top10 = df[df["ml_suggested_qty"] > 0].sort_values("stock_coverage_days").head(10)
    for _, row in top10.iterrows():
        cov = row["stock_coverage_days"]
        cov_str = f"{cov:.1f} days" if cov < 999 else "∞"
        print(
            f"    [{row['product_code']:12s}] {str(row['product_name'])[:30]:30s} "
            f"| {row['urgency_tier']:8s} | stock: {int(row['net_stock']):5d} | "
            f"suggest: {int(row['ml_suggested_qty']):5d} | coverage: {cov_str}"
        )
    print("─" * 60)


def main():
    parser = argparse.ArgumentParser(description="Sunrise Procurement ML Pipeline")
    parser.add_argument("--dry-run",        action="store_true", help="Print predictions without uploading")
    parser.add_argument("--skip-forecast",  action="store_true", help="Skip Prophet forecasting (faster)")
    parser.add_argument("--no-clear",       action="store_true", help="Do not clear existing Supabase records")
    args = parser.parse_args()

    print_banner()
    start = time.time()

    # ── STEP 1: Feature Engineering ──────────────────────────────────────────
    print("\n[1/5] Building feature matrix from Supabase data...")
    feature_df, date_range_days = build_feature_matrix()

    # ── STEP 2: Demand Forecasting ────────────────────────────────────────────
    if not args.skip_forecast:
        print("\n[2/5] Running demand forecasts...")
        sales_rows = fetch_table("His Sales")
        forecasts  = run_forecasts(sales_rows, feature_df)
    else:
        print("\n[2/5] Skipping Prophet — using linear extrapolation.")
        forecasts = {}

    # ── STEP 3: Train Models ─────────────────────────────────────────────────
    print("\n[3/5] Training ML models...")
    km_model, feature_df = train_kmeans(feature_df)     # returns (KMeans, labelled_df)
    xgb_model = train_xgboost(feature_df)
    rf_model  = train_random_forest(feature_df)

    # ── STEP 4: Predict ───────────────────────────────────────────────────────
    print("\n[4/5] Generating predictions...")
    pred_df = predict_all(feature_df, km_model, xgb_model, rf_model)

    # Override individual SKU forecasts where Prophet ran
    if forecasts:
        for code, f30 in forecasts.items():
            mask = pred_df["product_code"] == code
            if mask.any() and f30 > 0:
                pred_df.loc[mask, "avg_daily_qty_norm"] = f30 / 30.0

        # Recompute suggested_qty with updated velocities
        pred_df["reorder_point"] = np.ceil(pred_df["avg_daily_qty_norm"] * LEAD_TIME_DAYS).astype(int)
        from config import COVERAGE_TARGET, SAFETY_BUFFER_PCT
        optimal = np.ceil(pred_df["avg_daily_qty_norm"] * COVERAGE_TARGET)
        pred_df["ml_suggested_qty"] = np.maximum(
            0,
            np.ceil((optimal - pred_df["effective_stock"]) * (1 + SAFETY_BUFFER_PCT))
        ).astype(int)
        pred_df["optimal_level"]             = optimal.astype(int)
        pred_df["estimated_order_value_kwd"] = (pred_df["ml_suggested_qty"] * pred_df["cost_price"]).round(2)

    records = build_records(pred_df, forecasts)
    print_summary(pred_df, records)

    # ── STEP 5: Upload ────────────────────────────────────────────────────────
    print(f"\n[5/5] Uploading {len(records)} records to Supabase...")
    if not args.no_clear and not args.dry_run:
        clear_existing_records()
    upload_records(records, dry_run=args.dry_run)

    elapsed = time.time() - start
    print(f"\n✅ Pipeline completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
