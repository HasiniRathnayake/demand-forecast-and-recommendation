"""
models.py — ML model definitions and training
Project: 2026-Y2-S2-KU-AI-02

Models:
  1. K-Means  — SKU demand segmentation (Fast/Medium/Slow/Dead)
  2. XGBoost  — Predict suggested_qty (regression)
  3. Random Forest — Predict urgency tier (classification)
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, mean_absolute_error
import xgboost as xgb
from config import (
    N_CLUSTERS, XGB_N_ESTIMATORS, XGB_MAX_DEPTH, XGB_LEARNING_RATE,
    RF_N_ESTIMATORS, SAFETY_BUFFER_PCT, LEAD_TIME_DAYS, COVERAGE_TARGET
)

MODEL_DIR = Path(__file__).parent / "saved_models"
MODEL_DIR.mkdir(exist_ok=True)

# Cluster labels ordered by velocity (assigned post-training based on centroid)
CLUSTER_LABELS = {0: "Fast Mover", 1: "Medium Mover", 2: "Slow Mover", 3: "Dead Stock"}
URGENCY_TIERS  = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


# ── FEATURES USED ─────────────────────────────────────────────────────────────
CLUSTER_FEATURES = [
    "avg_daily_qty_norm", "cv_demand", "days_with_sales",
    "total_qty_sold", "total_revenue",
]
XGB_FEATURES = [
    "avg_daily_qty_norm", "cv_demand", "days_with_sales",
    "effective_stock", "pending_po_qty", "cost_price",
    "wastage_qty", "stock_coverage_days",
]
RF_FEATURES = XGB_FEATURES + ["cluster_id"]


# ── 1. K-MEANS SEGMENTATION ───────────────────────────────────────────────────

def train_kmeans(df: pd.DataFrame):
    """
    Cluster SKUs into four demand segments.
    Returns df with added 'cluster_id' and 'demand_segment' columns.
    """
    print("\n🔵 Training K-Means (SKU segmentation)...")
    X = df[CLUSTER_FEATURES].fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    df = df.copy()
    df["cluster_id"] = km.fit_predict(X_scaled)

    # Label clusters by avg daily qty (highest = Fast Mover)
    centroids = df.groupby("cluster_id")["avg_daily_qty_norm"].mean().sort_values(ascending=False)
    label_map = {cid: CLUSTER_LABELS[rank] for rank, cid in enumerate(centroids.index)}
    df["demand_segment"] = df["cluster_id"].map(label_map)

    # Save
    joblib.dump(km,     MODEL_DIR / "kmeans.pkl")
    joblib.dump(scaler, MODEL_DIR / "kmeans_scaler.pkl")

    seg_counts = df["demand_segment"].value_counts()
    for seg, cnt in seg_counts.items():
        print(f"   {seg}: {cnt} SKUs")

    return km, df   # ← (fitted KMeans model, labelled dataframe)


# ── 2. XGBOOST — suggested_qty regression ────────────────────────────────────

def _compute_rule_qty(df: pd.DataFrame) -> pd.Series:
    """
    Compute a 'ground truth' suggested_qty using the business formula.
    Used to generate training labels for XGBoost when we have no historical
    procurement approval labels.
    """
    optimal = np.ceil(df["avg_daily_qty_norm"] * COVERAGE_TARGET)
    suggest = np.maximum(0, np.ceil((optimal - df["effective_stock"]) * (1 + SAFETY_BUFFER_PCT)))
    return suggest.astype(int)


def train_xgboost(df: pd.DataFrame):
    """
    Train XGBoost regressor to predict suggested_qty.

    Since we don't yet have historical approved quantities, we use the business
    formula as training labels and let XGBoost learn a non-linear fit. When
    real approval labels are available (approved orders table), this function
    can be updated to use those instead.
    """
    print("\n🟠 Training XGBoost (suggested_qty regressor)...")

    df = df.copy()
    df["target_qty"] = _compute_rule_qty(df)

    # Filter to products that actually need reordering
    reorder_mask = (
        (df["avg_daily_qty_norm"] > 0) &
        (df["effective_stock"] <= np.ceil(df["avg_daily_qty_norm"] * LEAD_TIME_DAYS))
    )
    train_df = df[reorder_mask].copy()
    print(f"   Training on {len(train_df)} products flagged for reorder")

    if len(train_df) < 10:
        print("   ⚠️  Not enough reorder rows for XGBoost split — using all data instead.")
        train_df = df.copy()

    X = train_df[XGB_FEATURES].fillna(0)
    y = train_df["target_qty"]

    test_size = 0.2 if len(train_df) >= 20 else 0.0
    if test_size > 0:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
    else:
        X_train, X_test, y_train, y_test = X, X, y, y

    model = xgb.XGBRegressor(
        n_estimators    = XGB_N_ESTIMATORS,
        max_depth       = XGB_MAX_DEPTH,
        learning_rate   = XGB_LEARNING_RATE,
        objective       = "reg:squarederror",
        random_state    = 42,
        verbosity       = 0,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae   = mean_absolute_error(y_test, preds)
    print(f"   MAE on validation set: {mae:.2f} units")

    # Feature importance
    fi = pd.Series(model.feature_importances_, index=XGB_FEATURES).sort_values(ascending=False)
    print("   Top features:")
    for feat, imp in fi.head(4).items():
        print(f"      {feat}: {imp:.3f}")

    joblib.dump(model, MODEL_DIR / "xgboost_qty.pkl")
    return model


# ── 3. RANDOM FOREST — urgency classification ─────────────────────────────────

def _assign_urgency_label(df: pd.DataFrame) -> pd.Series:
    """
    Auto-label urgency tier based on stock_coverage_days.
      CRITICAL : coverage < 3 days
      HIGH     : coverage < 7 days
      MEDIUM   : coverage < 14 days
      LOW      : coverage >= 14 days
    """
    def label(row):
        cov = row.get("stock_coverage_days", 999)
        if cov < 3:   return "CRITICAL"
        if cov < 7:   return "HIGH"
        if cov < 14:  return "MEDIUM"
        return "LOW"

    return df.apply(label, axis=1)


def train_random_forest(df: pd.DataFrame):
    """
    Train Random Forest classifier to predict urgency tier.
    """
    print("\n🟢 Training Random Forest (urgency classifier)...")

    df = df.copy()
    df["urgency_tier"] = _assign_urgency_label(df)

    label_counts = df["urgency_tier"].value_counts()
    for tier, cnt in label_counts.items():
        print(f"   {tier}: {cnt} SKUs")

    X = df[RF_FEATURES].fillna(0)
    y = df["urgency_tier"]

    test_size = 0.2 if len(df) >= 20 else 0.0
    if test_size > 0:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
    else:
        X_train, X_test, y_train, y_test = X, X, y, y

    rf = RandomForestClassifier(
        n_estimators = RF_N_ESTIMATORS,
        max_depth    = 6,
        random_state = 42,
        class_weight = "balanced",
    )
    rf.fit(X_train, y_train)

    if test_size > 0:
        y_pred = rf.predict(X_test)
        print(classification_report(y_test, y_pred, zero_division=0))

    joblib.dump(rf, MODEL_DIR / "rf_urgency.pkl")
    return rf


# ── PREDICT (inference on full feature matrix) ────────────────────────────────

def predict_all(df: pd.DataFrame, km_model, xgb_model, rf_model) -> pd.DataFrame:
    """
    Run all three models on the full feature matrix and attach predictions.
    """
    df = df.copy()

    # --- K-Means segment ---
    scaler = joblib.load(MODEL_DIR / "kmeans_scaler.pkl")
    X_cluster = df[CLUSTER_FEATURES].fillna(0)
    X_scaled  = scaler.transform(X_cluster)
    df["cluster_id"] = km_model.predict(X_scaled)

    # Re-label clusters by centroid velocity
    centroids = df.groupby("cluster_id")["avg_daily_qty_norm"].mean().sort_values(ascending=False)
    label_map = {cid: CLUSTER_LABELS[rank] for rank, cid in enumerate(centroids.index)}
    df["demand_segment"] = df["cluster_id"].map(label_map)

    # --- XGBoost suggested_qty ---
    X_xgb = df[XGB_FEATURES].fillna(0)
    raw_qty = xgb_model.predict(X_xgb)
    df["ml_suggested_qty"] = np.maximum(0, np.round(raw_qty).astype(int))

    # --- Random Forest urgency ---
    X_rf = df[RF_FEATURES].fillna(0)
    df["urgency_tier"] = rf_model.predict(X_rf)

    # --- Reorder point & optimal level (derived from ML velocity) ---
    df["reorder_point"] = np.ceil(df["avg_daily_qty_norm"] * LEAD_TIME_DAYS).astype(int)
    df["optimal_level"] = np.ceil(df["avg_daily_qty_norm"] * COVERAGE_TARGET).astype(int)
    df["estimated_order_value_kwd"] = (df["ml_suggested_qty"] * df["cost_price"]).round(2)

    return df
