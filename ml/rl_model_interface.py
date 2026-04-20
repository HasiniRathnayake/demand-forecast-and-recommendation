"""
ml/rl_model_interface.py
Author: IT24103258

Loads the RL-retrained XGBoost model (xgboost_rl_v2.json).
Completely separate from friend's model_interface.py — does not modify it.
"""

from __future__ import annotations
import os
import glob
import numpy as np
from xgboost import XGBRegressor

# ── Constants ──────────────────────────────────────────────────────────────────
MODELS_DIR     = os.path.join(os.path.dirname(__file__), "models")
RL_MODEL_VERSION  = "xgboost_rl_v2"
RL_MODEL_ACCURACY = 98.5   # from walk-forward evaluation (Colab)
RL_MODEL_MAPE     = 1.23   # from walk-forward evaluation (Colab)

# ── Feature columns — exact 51 columns used during RL training ─────────────────
RL_FEATURE_COLS: list[str] = [
    "day_of_week", "is_weekend", "month", "quarter",
    "day_of_year", "week_of_year", "is_holiday", "is_pre_holiday",
    "is_month_start", "is_month_end", "is_quarter_end",
    "day_of_week_sin", "day_of_week_cos",
    "month_sin", "month_cos",
    "day_of_year_sin", "day_of_year_cos",
    "lag_1", "lag_7", "lag_14", "lag_30",
    "lag_diff_1_7", "lag_diff_7_30",
    "rolling_7_mean", "rolling_14_mean", "rolling_30_mean",
    "rolling_7_std", "rolling_7_max", "rolling_7_min",
    "trend_7_30", "expanding_mean",
    "is_promotion", "lag_1_x_promo", "promo_x_holiday",
    "promo_x_weekend", "promo_x_pre_holiday",
    "days_since_promo", "promo_response_rate",
    "category_encoded", "brand_encoded",
    "category_mean_sales", "brand_mean_sales",
    "category_median_sales", "brand_median_sales",
    "product_global_mean", "product_global_std",
    "product_global_max", "product_global_median",
    "qty_vs_category_avg", "qty_vs_brand_avg", "qty_vs_product_avg",
]


def load_rl_model() -> tuple[XGBRegressor, str]:
    """
    Loads the latest RL model from ml/models/.
    Automatically picks up v3, v4 etc. after retraining.
    Returns (model, version_string).
    """
    pattern = os.path.join(MODELS_DIR, "xgboost_rl_v*.json")
    files   = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(
            f"No RL model found in {MODELS_DIR}. "
            "Copy xgboost_rl_v2.json into ml/models/ first."
        )
    latest  = max(files, key=os.path.getctime)
    version = os.path.splitext(os.path.basename(latest))[0]
    model   = XGBRegressor()
    model.load_model(latest)
    return model, version


def rl_predict(model: XGBRegressor, features: dict) -> dict:
    """
    Makes a single prediction using the RL model.

    features : dict with keys matching RL_FEATURE_COLS
    returns  : dict with predicted_demand, confidence_level, model_version
    """
    try:
        arr = np.array(
            [[features[col] for col in RL_FEATURE_COLS]],
            dtype=float,
        )
    except KeyError as e:
        raise ValueError(f"Missing feature column: {e}")

    predicted = float(max(model.predict(arr)[0], 0))

    return {
        "predicted_demand" : round(predicted, 3),
        "confidence_level" : round(RL_MODEL_ACCURACY / 100, 4),
        "model_version"    : RL_MODEL_VERSION,
        "model_accuracy"   : RL_MODEL_ACCURACY,
    }