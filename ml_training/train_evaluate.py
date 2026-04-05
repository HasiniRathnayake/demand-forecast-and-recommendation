"""
ml_training/train_evaluate.py
==============================
Complete ML pipeline for Sunrise Supermarket Demand Forecasting.
Trains, evaluates, tunes XGBoost and Random Forest models.

Run from project root:
    python ml_training/train_evaluate.py

Outputs saved to ml_training/outputs/:
    xgboost_v1.pkl, rf_v1.pkl, model_metrics.json,
    feature_importance.png, evaluation_report.txt
"""

import os
import json
import pickle
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, cross_val_score
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
MODELS_DIR = os.path.join(os.path.dirname(BASE_DIR), "ml", "saved_models")
DATA_PATH  = os.path.join(BASE_DIR, "featured_sales_data.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

TARGET = "quantity_sold"

FEATURE_COLS = [
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


def load_and_prepare(path):
    print("\n" + "="*60)
    print("STEP 1: Loading and Preparing Data")
    print("="*60)
    df = pd.read_csv(path)
    print(f"  Loaded: {df.shape[0]} rows, {df.shape[1]} columns")
    print(f"  Products: {df['product_code'].nunique()} unique")
    print(f"  Date range: {df['transaction_date'].min()} to {df['transaction_date'].max()}")
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df = df.sort_values("transaction_date").reset_index(drop=True)
    df["days_since_promo"] = df["days_since_promo"].fillna(0)
    before = len(df)
    df = df[df[TARGET] > 0].reset_index(drop=True)
    print(f"  Removed {before - len(df)} zero-quantity rows. Final: {len(df)} rows")
    return df


def time_based_split(df, train_ratio=0.8):
    print("\n" + "="*60)
    print("STEP 2: Time-Based Train/Test Split (80/20)")
    print("="*60)
    split_idx = int(len(df) * train_ratio)
    train = df.iloc[:split_idx].copy()
    test  = df.iloc[split_idx:].copy()
    print(f"  Train: {len(train)} rows  ({train['transaction_date'].min().date()} to {train['transaction_date'].max().date()})")
    print(f"  Test:  {len(test)} rows  ({test['transaction_date'].min().date()} to {test['transaction_date'].max().date()})")
    X_train = train[FEATURE_COLS]
    y_train = train[TARGET]
    X_test  = test[FEATURE_COLS]
    y_test  = test[TARGET]
    return X_train, y_train, X_test, y_test, train, test


def compute_metrics(y_true, y_pred, model_name):
    mae  = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2   = float(r2_score(y_true, y_pred))
    with np.errstate(divide="ignore", invalid="ignore"):
        mape_arr = np.where(np.array(y_true) != 0,
                            np.abs((np.array(y_true) - y_pred) / np.array(y_true)), 0)
    mape = float(np.mean(mape_arr) * 100)
    print(f"\n  {model_name} Test Results:")
    print(f"    MAPE  : {mape:.2f}%")
    print(f"    RMSE  : {rmse:.2f}")
    print(f"    MAE   : {mae:.2f}")
    print(f"    R2    : {r2:.4f}")
    return {"model": model_name, "mape": round(mape,2), "rmse": round(rmse,2),
            "mae": round(mae,2), "r2_score": round(r2,4)}


def train_xgboost(X_train, y_train):
    print("\n" + "="*60)
    print("STEP 3a: Training XGBoost (initial)")
    print("="*60)
    model = XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05,
                         subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                         reg_alpha=0.1, reg_lambda=1.0, random_state=42,
                         n_jobs=-1, verbosity=0)
    model.fit(X_train, y_train, eval_set=[(X_train, y_train)], verbose=False)
    cv = cross_val_score(XGBRegressor(n_estimators=100, max_depth=6,
                                       learning_rate=0.05, random_state=42, verbosity=0),
                         X_train, y_train, cv=5, scoring="r2", n_jobs=-1)
    print(f"  XGBoost training complete.")
    print(f"  Cross-validation R2 (5-fold): {cv.mean():.4f} +/- {cv.std():.4f}")
    return model


def train_random_forest(X_train, y_train):
    print("\n" + "="*60)
    print("STEP 3b: Training Random Forest (initial)")
    print("="*60)
    model = RandomForestRegressor(n_estimators=200, max_depth=10,
                                   min_samples_split=5, min_samples_leaf=2,
                                   max_features="sqrt", random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    cv = cross_val_score(RandomForestRegressor(n_estimators=100, max_depth=10,
                                                random_state=42, n_jobs=-1),
                         X_train, y_train, cv=5, scoring="r2", n_jobs=-1)
    print(f"  Random Forest training complete.")
    print(f"  Cross-validation R2 (5-fold): {cv.mean():.4f} +/- {cv.std():.4f}")
    return model


def tune_xgboost(X_train, y_train):
    print("\n" + "="*60)
    print("STEP 4: Hyperparameter Tuning (XGBoost Grid Search)")
    print("="*60)
    param_grid = {
        "max_depth":     [4, 6],
        "learning_rate": [0.05, 0.1],
        "n_estimators":  [200, 300],
        "subsample":     [0.8],
    }
    base = XGBRegressor(random_state=42, n_jobs=-1, verbosity=0,
                        colsample_bytree=0.8, min_child_weight=3,
                        reg_alpha=0.1, reg_lambda=1.0)
    grid = GridSearchCV(base, param_grid, cv=3,
                        scoring="neg_mean_absolute_error",
                        n_jobs=-1, verbose=1)
    grid.fit(X_train, y_train)
    print(f"\n  Best parameters: {grid.best_params_}")
    print(f"  Best CV MAE:     {-grid.best_score_:.4f}")
    best = XGBRegressor(**grid.best_params_, colsample_bytree=0.8,
                        min_child_weight=3, reg_alpha=0.1, reg_lambda=1.0,
                        random_state=42, n_jobs=-1, verbosity=0)
    best.fit(X_train, y_train, verbose=False)
    print("  Tuned XGBoost re-trained on full training set.")
    return best


def plot_feature_importance(xgb_model, rf_model):
    print("  Generating feature importance plots...")
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    xgb_imp = pd.Series(xgb_model.feature_importances_, index=FEATURE_COLS)
    xgb_top = xgb_imp.nlargest(15).sort_values()
    axes[0].barh(xgb_top.index, xgb_top.values, color="#2563EB")
    axes[0].set_title("XGBoost - Top 15 Feature Importances", fontsize=13, fontweight="bold")
    axes[0].set_xlabel("Importance Score")
    rf_imp = pd.Series(rf_model.feature_importances_, index=FEATURE_COLS)
    rf_top = rf_imp.nlargest(15).sort_values()
    axes[1].barh(rf_top.index, rf_top.values, color="#059669")
    axes[1].set_title("Random Forest - Top 15 Feature Importances", fontsize=13, fontweight="bold")
    axes[1].set_xlabel("Importance Score")
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "feature_importance.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def plot_predictions(test_df, xgb_pred, rf_pred, winner):
    print("  Generating actual vs predicted plots...")
    sample   = test_df.reset_index(drop=True).head(100)
    xgb_s    = xgb_pred[:100]
    rf_s     = rf_pred[:100]
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))
    x = range(len(sample))
    axes[0].plot(x, sample[TARGET].values, label="Actual", color="black", linewidth=1.5)
    axes[0].plot(x, xgb_s, label="XGBoost Predicted", color="#2563EB", linestyle="--", linewidth=1.5)
    axes[0].set_title("XGBoost - Actual vs Predicted (first 100 test samples)", fontsize=12, fontweight="bold")
    axes[0].legend()
    axes[0].set_ylabel("Quantity Sold")
    axes[0].grid(True, alpha=0.3)
    axes[1].plot(x, sample[TARGET].values, label="Actual", color="black", linewidth=1.5)
    axes[1].plot(x, rf_s, label="RF Predicted", color="#059669", linestyle="--", linewidth=1.5)
    axes[1].set_title("Random Forest - Actual vs Predicted (first 100 test samples)", fontsize=12, fontweight="bold")
    axes[1].legend()
    axes[1].set_ylabel("Quantity Sold")
    axes[1].set_xlabel("Sample Index")
    axes[1].grid(True, alpha=0.3)
    plt.suptitle(f"Model Evaluation - Winner: {winner.upper()}", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "actual_vs_predicted.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def compare_and_decide(xgb_metrics, rf_metrics):
    print("\n" + "="*60)
    print("STEP 6: Model Comparison")
    print("="*60)
    score_xgb = xgb_metrics["r2_score"] - (xgb_metrics["mape"] / 100)
    score_rf  = rf_metrics["r2_score"]  - (rf_metrics["mape"] / 100)
    print(f"\n  {'Metric':<12} {'XGBoost':>12} {'Random Forest':>15}")
    print(f"  {'-'*42}")
    print(f"  {'MAPE':<12} {xgb_metrics['mape']:>11.2f}% {rf_metrics['mape']:>14.2f}%")
    print(f"  {'RMSE':<12} {xgb_metrics['rmse']:>12.2f} {rf_metrics['rmse']:>15.2f}")
    print(f"  {'MAE':<12} {xgb_metrics['mae']:>12.2f} {rf_metrics['mae']:>15.2f}")
    print(f"  {'R2':<12} {xgb_metrics['r2_score']:>12.4f} {rf_metrics['r2_score']:>15.4f}")
    print(f"  {'Score':<12} {score_xgb:>12.4f} {score_rf:>15.4f}")
    print(f"  {'-'*42}")
    winner = "xgboost" if score_xgb >= score_rf else "random_forest"
    margin = "by a clear margin" if abs(score_xgb - score_rf) > 0.02 else "narrowly"
    print(f"\n  Winner: {winner.upper()} ({margin})")
    return winner


def save_all(xgb_model, rf_model, xgb_metrics, rf_metrics, winner):
    print("\n" + "="*60)
    print("STEP 7: Saving Models and Metrics")
    print("="*60)
    for directory in [OUTPUT_DIR, MODELS_DIR]:
        with open(os.path.join(directory, "xgboost_v1.pkl"), "wb") as f:
            pickle.dump(xgb_model, f)
        with open(os.path.join(directory, "rf_v1.pkl"), "wb") as f:
            pickle.dump(rf_model, f)
        print(f"  Models saved to: {directory}")
    metrics_data = {
        "trained_at":    datetime.now().isoformat(),
        "winner":        winner,
        "active_model":  winner,
        "feature_cols":  FEATURE_COLS,
        "dataset_info":  {
            "total_rows":   20117,
            "products":     30,
            "date_range":   "2024-03-01 to 2025-12-31",
            "train_split":  "80%",
            "test_split":   "20%",
        },
        "xgboost":       xgb_metrics,
        "random_forest": rf_metrics,
    }
    for directory in [OUTPUT_DIR, MODELS_DIR]:
        with open(os.path.join(directory, "model_metrics.json"), "w") as f:
            json.dump(metrics_data, f, indent=2)
    report_path = os.path.join(OUTPUT_DIR, "evaluation_report.txt")
    with open(report_path, "w") as f:
        f.write("="*60 + "\n")
        f.write("SUNRISE SUPERMARKET - MODEL EVALUATION REPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
        f.write(f"WINNER: {winner.upper()}\n\n")
        f.write("XGBoost:\n")
        for k, v in xgb_metrics.items():
            f.write(f"  {k}: {v}\n")
        f.write("\nRandom Forest:\n")
        for k, v in rf_metrics.items():
            f.write(f"  {k}: {v}\n")
    print(f"  Metrics JSON and report saved.")


def main():
    print("\n" + "="*60)
    print("  SUNRISE SUPERMARKET - ML TRAINING PIPELINE")
    print("  XGBoost vs Random Forest | Demand Forecasting")
    print("="*60)
    df = load_and_prepare(DATA_PATH)
    X_train, y_train, X_test, y_test, train_df, test_df = time_based_split(df)
    xgb_model = train_xgboost(X_train, y_train)
    rf_model  = train_random_forest(X_train, y_train)
    xgb_model = tune_xgboost(X_train, y_train)
    print("\n" + "="*60)
    print("STEP 5: Final Evaluation on Test Set")
    print("="*60)
    xgb_pred    = xgb_model.predict(X_test)
    rf_pred     = rf_model.predict(X_test)
    xgb_metrics = compute_metrics(y_test, xgb_pred, "XGBoost")
    rf_metrics  = compute_metrics(y_test, rf_pred,  "Random Forest")
    winner      = compare_and_decide(xgb_metrics, rf_metrics)
    print("\n" + "="*60)
    print("STEP 5b: Evaluation Plots")
    print("="*60)
    plot_feature_importance(xgb_model, rf_model)
    plot_predictions(test_df, xgb_pred, rf_pred, winner)
    save_all(xgb_model, rf_model, xgb_metrics, rf_metrics, winner)
    print("\n" + "="*60)
    print(f"  DONE. Winner: {winner.upper()}")
    print(f"  Models saved in: {MODELS_DIR}")
    print(f"  Reports in:      {OUTPUT_DIR}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()