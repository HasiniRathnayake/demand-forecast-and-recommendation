

from __future__ import annotations
import pandas as pd
import numpy as np


# ── Core metrics ───────────────────────────────────────────────────────────────

def calculate_metrics(history_df: pd.DataFrame) -> dict:
    """
    Compute MAPE, RMSE, MAE, and R² from a historical sales DataFrame.

    Parameters
    ----------
    history_df : DataFrame with at least a 'quantity_sold' column.

    Returns
    -------
    dict with keys: mape, rmse, mae, r2_score
    """
    if history_df is None or history_df.empty:
        return _zero_metrics()

    if "quantity_sold" not in history_df.columns:
        raise ValueError(
            "history_df must contain a 'quantity_sold' column. "
            f"Got columns: {list(history_df.columns)}"
        )

    sales = history_df["quantity_sold"].dropna().values

    if len(sales) < 2:
        return _zero_metrics()

    mean_sales = float(np.mean(sales))
    rolling_mean = pd.Series(sales).rolling(7, min_periods=1).mean().values
    errors = sales - rolling_mean

    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    with np.errstate(divide="ignore", invalid="ignore"):
        mape_arr = np.where(sales != 0, np.abs(errors / sales), 0.0)
    mape = float(np.mean(mape_arr) * 100)

    ss_res = float(np.sum(errors ** 2))
    ss_tot = float(np.sum((sales - mean_sales) ** 2))
    r2 = (1.0 - ss_res / ss_tot) if ss_tot != 0 else 0.0
    r2 = max(0.0, min(1.0, r2))

    return {
        "mape":     round(mape, 2),
        "rmse":     round(rmse, 2),
        "mae":      round(mae, 2),
        "r2_score": round(r2, 4),
    }


# ── Accuracy grade label ───────────────────────────────────────────────────────

def accuracy_grade(metrics: dict) -> dict:
    """
    Translate numeric metrics into human-readable grade labels
    so the dashboard can display them without raw numbers alone.

    Returns the original metrics dict enriched with:
        grade       : "Excellent" | "Good" | "Fair" | "Poor"
        grade_color : hex colour matching the grade
        grade_emoji : emoji for quick visual
    """
    r2 = metrics.get("r2_score", 0.0)
    mape = metrics.get("mape", 100.0)

    if r2 >= 0.85 and mape <= 10:
        grade, color, emoji = "Excellent", "#059669", "🟢"
    elif r2 >= 0.70 and mape <= 20:
        grade, color, emoji = "Good",      "#2563EB", "🔵"
    elif r2 >= 0.50 and mape <= 35:
        grade, color, emoji = "Fair",      "#D97706", "🟡"
    else:
        grade, color, emoji = "Poor",      "#DC2626", "🔴"

    return {
        **metrics,
        "grade":       grade,
        "grade_color": color,
        "grade_emoji": emoji,
    }


# ── Model comparison ───────────────────────────────────────────────────────────

def compare_models(metrics_a: dict, metrics_b: dict, label_a: str = "Model A", label_b: str = "Model B") -> dict:
    """
    Compare two sets of accuracy metrics and declare a winner.

    Used in Progress 3 to compare XGBoost vs Random Forest.

    Returns
    -------
    dict with:
        winner      : label of the better model
        summary     : human-readable comparison string
        delta_r2    : r2_score(A) - r2_score(B)
        delta_mape  : mape(A) - mape(B)  (negative = A is better)
    """
    r2_a = metrics_a.get("r2_score", 0.0)
    r2_b = metrics_b.get("r2_score", 0.0)
    mape_a = metrics_a.get("mape", 100.0)
    mape_b = metrics_b.get("mape", 100.0)

    # Score: higher R² and lower MAPE wins
    score_a = r2_a - (mape_a / 100)
    score_b = r2_b - (mape_b / 100)

    if score_a >= score_b:
        winner = label_a
        diff = abs(score_a - score_b)
        margin = "by a clear margin" if diff > 0.05 else "narrowly"
    else:
        winner = label_b
        diff = abs(score_a - score_b)
        margin = "by a clear margin" if diff > 0.05 else "narrowly"

    return {
        "winner":     winner,
        "summary":    f"{winner} wins {margin}. R²: {label_a}={r2_a:.3f} vs {label_b}={r2_b:.3f}. MAPE: {label_a}={mape_a:.1f}% vs {label_b}={mape_b:.1f}%.",
        "delta_r2":   round(r2_a - r2_b, 4),
        "delta_mape": round(mape_a - mape_b, 2),
        label_a:      accuracy_grade(metrics_a),
        label_b:      accuracy_grade(metrics_b),
    }


# ── Threshold checker ──────────────────────────────────────────────────────────

def meets_production_threshold(metrics: dict) -> tuple[bool, str]:
    """
    Check whether a model's metrics meet the minimum bar for production use.

    Thresholds (adjust as needed once real data is available):
        R² >= 0.65
        MAPE <= 25%

    Returns
    -------
    (passes: bool, message: str)
    """
    r2   = metrics.get("r2_score", 0.0)
    mape = metrics.get("mape", 100.0)

    if r2 >= 0.65 and mape <= 25.0:
        return True, f"✅ Model meets production threshold (R²={r2:.3f}, MAPE={mape:.1f}%)"
    else:
        reasons = []
        if r2 < 0.65:
            reasons.append(f"R²={r2:.3f} is below 0.65")
        if mape > 25.0:
            reasons.append(f"MAPE={mape:.1f}% exceeds 25%")
        return False, f"❌ Model does not meet threshold: {'; '.join(reasons)}"


# ── private ────────────────────────────────────────────────────────────────────

def _zero_metrics() -> dict:
    return {"mape": 0.0, "rmse": 0.0, "mae": 0.0, "r2_score": 0.0}

"""
services/accuracy_service.py
=============================
Standalone accuracy / evaluation service.

Centralises all model-performance calculations so:
  - The dashboard can call it independently of the forecaster
  - The real XGBoost/RF models can plug in their own metrics later
  - Tests can import this without touching the ML layer

Internally delegates to BaseForecaster.calculate_accuracy_metrics()
for the actual maths, but also adds higher-level helpers (grade labels,
comparison between two models, threshold checks).
"""