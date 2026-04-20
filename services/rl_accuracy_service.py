"""
services/rl_accuracy_service.py
Author: IT24103258

Reward scoring logic for the RL model.
Completely separate from friend's accuracy_service.py.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


# ── Reward function settings (same as Colab training) ─────────────────────────
WASTE_COST     = 2.0    # cost per unit over-predicted
STOCKOUT_COST  = 5.0    # cost per unit under-predicted
PERFECT_BONUS  = 10.0   # reward for prediction within tolerance
TOLERANCE      = 0.05   # 5% error = perfect


def calculate_reward(actual: float, predicted: float) -> float:
    """
    Calculates a reward score for a single prediction.
    Matches exactly the reward function used in Colab training.

    Positive reward = good prediction
    Negative reward = bad prediction (waste or stockout)
    """
    actual    = float(actual)
    predicted = float(predicted)

    if actual == 0:
        return 0.0

    diff      = predicted - actual
    pct_error = abs(diff) / actual

    if pct_error <= TOLERANCE:
        return PERFECT_BONUS
    elif diff > 0:                        # over-predicted → waste
        return round(-(diff * WASTE_COST), 4)
    else:                                 # under-predicted → stockout
        return round(-(abs(diff) * STOCKOUT_COST), 4)


def score_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a 'reward' column to a DataFrame that has
    'actual_sales' and 'predicted_demand' columns.
    Only scores rows where actual_sales is not null.
    """
    df = df.copy()
    mask = df["actual_sales"].notna()
    df.loc[mask, "reward"] = df[mask].apply(
        lambda r: calculate_reward(r["actual_sales"], r["predicted_demand"]),
        axis=1,
    )
    return df


def rl_summary_metrics(df: pd.DataFrame) -> dict:
    """
    Computes summary metrics for the RL performance dashboard.
    Input df must have 'reward', 'actual_sales', 'predicted_demand' columns.
    """
    evaluated = df[df["actual_sales"].notna()].copy()
    if evaluated.empty:
        return {}

    evaluated = score_predictions(evaluated)
    rewards   = evaluated["reward"].values

    perfect_pct = float((rewards == PERFECT_BONUS).mean() * 100)
    avg_reward  = float(np.mean(rewards))

    errors = np.abs(
        evaluated["actual_sales"].values - evaluated["predicted_demand"].values
    )
    mae  = float(np.mean(errors))
    mape = float(np.mean(
        np.where(
            evaluated["actual_sales"].values != 0,
            errors / evaluated["actual_sales"].values,
            0,
        )
    ) * 100)

    return {
        "count"       : len(evaluated),
        "avg_reward"  : round(avg_reward, 2),
        "perfect_pct" : round(perfect_pct, 1),
        "mae"         : round(mae, 3),
        "mape"        : round(mape, 2),
    }