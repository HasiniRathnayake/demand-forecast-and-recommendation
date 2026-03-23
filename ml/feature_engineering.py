
from __future__ import annotations
import pandas as pd
import numpy as np
from config.settings import ALL_PUBLIC_HOLIDAYS


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform a raw sales history DataFrame into an ML feature matrix.

    Expected input columns:
        transaction_date, quantity_sold, is_promotion (optional)

    Returns a DataFrame with engineered features ready for XGBoost/RF.
    """
    df = df.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df = df.sort_values("transaction_date").reset_index(drop=True)

    # ── Calendar features ──────────────────────────────────────────────────────
    df["day_of_week"] = df["transaction_date"].dt.dayofweek        # 0=Mon … 6=Sun
    df["day_of_month"] = df["transaction_date"].dt.day
    df["week_of_year"] = df["transaction_date"].dt.isocalendar().week.astype(int)
    df["month"] = df["transaction_date"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_public_holiday"] = df["transaction_date"].dt.date.astype(str).isin(
        ALL_PUBLIC_HOLIDAYS
    ).astype(int)

    # ── Lag features ───────────────────────────────────────────────────────────
    for lag in [1, 7, 14, 30]:
        df[f"lag_{lag}d"] = df["quantity_sold"].shift(lag)

    # ── Rolling statistics ─────────────────────────────────────────────────────
    for window in [7, 14, 30]:
        df[f"rolling_mean_{window}d"] = (
            df["quantity_sold"].rolling(window, min_periods=1).mean()
        )
        df[f"rolling_std_{window}d"] = (
            df["quantity_sold"].rolling(window, min_periods=1).std().fillna(0)
        )

    # ── Promotion flag ─────────────────────────────────────────────────────────
    if "is_promotion" in df.columns:
        df["is_promotion"] = df["is_promotion"].fillna(False).astype(int)
    else:
        df["is_promotion"] = 0

    # Drop rows with NaN lags (first 30 days)
    df = df.dropna(subset=[f"lag_{lag}d" for lag in [1, 7, 14, 30]])

    feature_cols = [
        "day_of_week", "day_of_month", "week_of_year", "month",
        "is_weekend", "is_public_holiday", "is_promotion",
        "lag_1d", "lag_7d", "lag_14d", "lag_30d",
        "rolling_mean_7d", "rolling_mean_14d", "rolling_mean_30d",
        "rolling_std_7d", "rolling_std_14d", "rolling_std_30d",
    ]

    return df[feature_cols]


def get_feature_names() -> list[str]:
    """Return the ordered list of feature names used by the model."""
    return [
        "day_of_week", "day_of_month", "week_of_year", "month",
        "is_weekend", "is_public_holiday", "is_promotion",
        "lag_1d", "lag_7d", "lag_14d", "lag_30d",
        "rolling_mean_7d", "rolling_mean_14d", "rolling_mean_30d",
        "rolling_std_7d", "rolling_std_14d", "rolling_std_30d",
    ]


"""
ml/feature_engineering.py
==========================
Shared feature-engineering utilities.
Used by both mock forecaster (to show what features will be used)
and future real XGBoost/RF models.

To train the real model:
1. Load raw sales history into a DataFrame
2. Call build_features(df) to produce the feature matrix X
3. Target y = df["quantity_sold"]
4. Split, train, and save the model as ml/saved_models/xgboost_v1.pkl
"""
