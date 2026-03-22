"""
utils/helpers.py
────────────────
Formatting utilities and shared metric calculations.

Author : IT24103258
Module : Waste & Performance Monitor
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTING
# ─────────────────────────────────────────────────────────────────────────────

def format_lkr(amount) -> str:
    """Format a numeric value as Sri Lankan Rupees."""
    try:
        return f"Rs. {float(amount):,.2f}"
    except (TypeError, ValueError):
        return "Rs. 0.00"


def fmt_date(val) -> str:
    """Return YYYY-MM-DD string from a datetime/date value."""
    if pd.isna(val) or val is None:
        return "-"
    try:
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    except Exception:
        return "-"


def fmt_datetime(val) -> str:
    """Return YYYY-MM-DD HH:MM string from a datetime value."""
    if pd.isna(val) or val is None:
        return "-"
    try:
        return pd.to_datetime(val).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"


def fmt_float(val, decimals: int = 2) -> str:
    """Format a float to a fixed number of decimal places, or '-' if null."""
    if pd.isna(val) or val is None:
        return "-"
    try:
        return f"{float(val):.{decimals}f}"
    except (TypeError, ValueError):
        return "-"


def fmt_signed(val, decimals: int = 2) -> str:
    """Format a float with an explicit +/- sign."""
    if pd.isna(val) or val is None:
        return "-"
    try:
        return f"{float(val):+.{decimals}f}"
    except (TypeError, ValueError):
        return "-"


def fmt_pct(val, decimals: int = 2) -> str:
    """Format a float as a percentage string."""
    if pd.isna(val) or val is None:
        return "Pending"
    try:
        return f"{float(val):.{decimals}f}%"
    except (TypeError, ValueError):
        return "Pending"


# ─────────────────────────────────────────────────────────────────────────────
# AI ACCURACY METRICS  (no sklearn dependency)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_accuracy_metrics(df: pd.DataFrame) -> dict | None:
    """
    Calculate MAE, RMSE and MAPE from an ai_performance DataFrame.
    Requires columns: actual_sales, predicted_demand.
    Returns None if there are no evaluated rows.
    """
    if df.empty or "actual_sales" not in df.columns or "predicted_demand" not in df.columns:
        return None

    subset = df[df["actual_sales"].notna()].copy()
    if subset.empty:
        return None

    actual    = subset["actual_sales"].values.astype(float)
    predicted = subset["predicted_demand"].values.astype(float)
    errors    = actual - predicted

    mae  = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    with np.errstate(divide="ignore", invalid="ignore"):
        mape = float(np.mean(np.abs((actual - predicted) / actual)) * 100)
        if np.isnan(mape) or np.isinf(mape):
            mape = 0.0

    return {
        "mae":   mae,
        "rmse":  rmse,
        "mape":  mape,
        "count": len(subset),
    }
