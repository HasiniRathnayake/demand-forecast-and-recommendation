"""
scripts/rl_retrainer.py
Author: IT24103258

Monthly RL retraining script.
Run manually or schedule with cron / GitHub Actions.
Reads real reward data from ai_performance table,
retrains model, saves new version to ml/models/.

Usage:
    python scripts/rl_retrainer.py
"""

from __future__ import annotations
import os
import sys
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

# ── Make project root importable ──────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.db_client              import get_client
from ml.rl_model_interface       import RL_FEATURE_COLS, MODELS_DIR
from services.rl_accuracy_service import calculate_reward

MIN_ROWS_TO_RETRAIN = 500   # don't retrain on too little data


def fetch_reward_data() -> pd.DataFrame:
    """
    Fetches evaluated rows from ai_performance (rows with actual_sales filled in).
    These are used as training data for the next RL version.
    """
    client = get_client()
    resp = (
        client.table("ai_performance")
        .select("*")
        .not_.is_("actual_sales", "null")
        .execute()
    )
    if not resp.data:
        return pd.DataFrame()
    return pd.DataFrame(resp.data)


def reward_to_weights(rewards: np.ndarray, min_weight: float = 0.01, power: float = 2.0) -> np.ndarray:
    """
    Converts reward scores into sample weights.
    Uses power scaling for stronger contrast between good and bad predictions.
    Matches the reward_to_weights_v2 function used in Colab.
    """
    shifted = rewards - rewards.min() + min_weight
    powered = np.power(shifted, power)
    return powered / powered.mean()


def get_next_version() -> str:
    """
    Reads existing model files and returns the next version string.
    e.g. if v2 exists → returns 'xgboost_rl_v3'
    """
    import glob
    existing = glob.glob(os.path.join(MODELS_DIR, "xgboost_rl_v*.json"))
    if not existing:
        return "xgboost_rl_v3"
    versions = []
    for f in existing:
        try:
            num = int(os.path.splitext(os.path.basename(f))[0].split("_v")[-1])
            versions.append(num)
        except ValueError:
            pass
    next_num = max(versions) + 1 if versions else 3
    return f"xgboost_rl_v{next_num}"


def retrain() -> None:
    print(f"\n{'='*55}")
    print(f"  RL Retraining — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}")

    # 1 — Fetch real reward data from Supabase
    df = fetch_reward_data()
    if df.empty or len(df) < MIN_ROWS_TO_RETRAIN:
        print(f"  Not enough data to retrain. "
              f"Need {MIN_ROWS_TO_RETRAIN} rows, got {len(df)}.")
        return

    print(f"  Rows available : {len(df)}")

    # 2 — Calculate reward for each row
    df["reward"] = df.apply(
        lambda r: calculate_reward(r["actual_sales"], r["predicted_demand"]),
        axis=1,
    )
    print(f"  Avg reward     : {df['reward'].mean():.2f}")
    print(f"  Perfect rows   : {(df['reward'] == 10.0).mean()*100:.1f}%")

    # 3 — Check feature columns are present
    missing = [c for c in RL_FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"  WARNING: Missing feature columns: {missing}")
        print("  Cannot retrain without full feature set.")
        return

    X = df[RL_FEATURE_COLS].values
    y = df["predicted_demand"].values   # target: quantity to order
    w = reward_to_weights(df["reward"].values)

    # 4 — Retrain
    print("\n  Retraining XGBoost with reward weights...")
    model = XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X, y, sample_weight=w)

    # 5 — Save new version
    os.makedirs(MODELS_DIR, exist_ok=True)
    version   = get_next_version()
    save_path = os.path.join(MODELS_DIR, f"{version}.json")
    model.save_model(save_path)

    size_kb = os.path.getsize(save_path) / 1024
    print(f"\n  ✅ Saved: {save_path}  ({size_kb:.1f} KB)")
    print(f"  New version: {version}")
    print(f"  Website will automatically use this version on next load.")
    print(f"\n{'='*55}\n")


if __name__ == "__main__":
    retrain()