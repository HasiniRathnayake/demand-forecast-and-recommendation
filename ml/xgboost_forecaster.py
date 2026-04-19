"""
ml/xgboost_forecaster.py
=========================
Hybrid forecaster: uses XGBoost model patterns scaled to match
actual product sales from the database.

The model learned day-of-week, holiday, and seasonal PATTERNS from training.
We extract these relative patterns and apply them to the product's actual
recent mean sales from the database. This gives realistic, product-specific
predictions that match historical sales levels.
"""

from __future__ import annotations
import os, json, pickle, math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ml.model_interface import BaseForecaster
from config.settings import ALL_PUBLIC_HOLIDAYS

MODELS_DIR = os.path.join(os.path.dirname(__file__), "saved_models")

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

# Per-product features from actual featured_sales_data.csv
PRODUCT_FEATURES = {
    "BEV093": {"category_encoded":0,"brand_encoded":2,"category_mean_sales":94.75,"brand_mean_sales":89.54,"category_median_sales":87.89,"brand_median_sales":76.88,"product_global_mean":134.69,"product_global_std":36.83,"product_global_max":278.6,"product_global_median":126.49,"promo_response_rate":1.1514},
    "BEV122": {"category_encoded":0,"brand_encoded":2,"category_mean_sales":94.75,"brand_mean_sales":89.54,"category_median_sales":87.89,"brand_median_sales":76.88,"product_global_mean":75.08,"product_global_std":20.6,"product_global_max":157.48,"product_global_median":70.6,"promo_response_rate":1.1577},
    "BEV164": {"category_encoded":0,"brand_encoded":15,"category_mean_sales":94.75,"brand_mean_sales":95.84,"category_median_sales":87.89,"brand_median_sales":90.23,"product_global_mean":95.84,"product_global_std":26.45,"product_global_max":205.55,"product_global_median":90.23,"promo_response_rate":1.093},
    "BEV201": {"category_encoded":0,"brand_encoded":3,"category_mean_sales":94.75,"brand_mean_sales":109.34,"category_median_sales":87.89,"brand_median_sales":102.5,"product_global_mean":109.34,"product_global_std":30.56,"product_global_max":241.58,"product_global_median":102.5,"promo_response_rate":1.1696},
    "BEV205": {"category_encoded":0,"brand_encoded":2,"category_mean_sales":94.75,"brand_mean_sales":89.54,"category_median_sales":87.89,"brand_median_sales":76.88,"product_global_mean":58.79,"product_global_std":16.1,"product_global_max":121.34,"product_global_median":55.32,"promo_response_rate":1.1514},
    "DAI085": {"category_encoded":1,"brand_encoded":6,"category_mean_sales":57.96,"brand_mean_sales":57.86,"category_median_sales":55.12,"brand_median_sales":55.3,"product_global_mean":31.16,"product_global_std":6.86,"product_global_max":52.97,"product_global_median":30.05,"promo_response_rate":1.1363},
    "DAI092": {"category_encoded":1,"brand_encoded":0,"category_mean_sales":57.96,"brand_mean_sales":73.34,"category_median_sales":55.12,"brand_median_sales":69.78,"product_global_mean":73.34,"product_global_std":18.79,"product_global_max":164.96,"product_global_median":69.78,"promo_response_rate":1.1902},
    "DAI094": {"category_encoded":1,"brand_encoded":5,"category_mean_sales":57.96,"brand_mean_sales":42.91,"category_median_sales":55.12,"brand_median_sales":40.31,"product_global_mean":42.91,"product_global_std":12.51,"product_global_max":121.39,"product_global_median":40.31,"promo_response_rate":1.1762},
    "DAI101": {"category_encoded":1,"brand_encoded":6,"category_mean_sales":57.96,"brand_mean_sales":57.86,"category_median_sales":55.12,"brand_median_sales":55.3,"product_global_mean":84.23,"product_global_std":18.66,"product_global_max":148.77,"product_global_median":81.01,"promo_response_rate":1.1814},
    "DAI103": {"category_encoded":1,"brand_encoded":6,"category_mean_sales":57.96,"brand_mean_sales":57.86,"category_median_sales":55.12,"brand_median_sales":55.3,"product_global_mean":58.09,"product_global_std":13.33,"product_global_max":105.43,"product_global_median":55.26,"promo_response_rate":1.1903},
    "FLO051": {"category_encoded":2,"brand_encoded":11,"category_mean_sales":44.84,"brand_mean_sales":87.59,"category_median_sales":39.04,"brand_median_sales":83.25,"product_global_mean":87.59,"product_global_std":21.71,"product_global_max":165.0,"product_global_median":83.25,"promo_response_rate":1.1551},
    "FLO073": {"category_encoded":2,"brand_encoded":14,"category_mean_sales":44.84,"brand_mean_sales":51.98,"category_median_sales":39.04,"brand_median_sales":46.65,"product_global_mean":47.97,"product_global_std":14.56,"product_global_max":127.6,"product_global_median":44.77,"promo_response_rate":1.1696},
    "FLO084": {"category_encoded":2,"brand_encoded":8,"category_mean_sales":44.84,"brand_mean_sales":37.54,"category_median_sales":39.04,"brand_median_sales":35.52,"product_global_mean":37.54,"product_global_std":9.31,"product_global_max":66.27,"product_global_median":35.52,"promo_response_rate":1.2132},
    "FLO102": {"category_encoded":2,"brand_encoded":13,"category_mean_sales":44.84,"brand_mean_sales":38.92,"category_median_sales":39.04,"brand_median_sales":36.68,"product_global_mean":38.92,"product_global_std":10.0,"product_global_max":75.08,"product_global_median":36.68,"promo_response_rate":1.2128},
    "FLO105": {"category_encoded":2,"brand_encoded":16,"category_mean_sales":44.84,"brand_mean_sales":12.35,"category_median_sales":39.04,"brand_median_sales":11.64,"product_global_mean":12.35,"product_global_std":3.34,"product_global_max":27.1,"product_global_median":11.64,"promo_response_rate":1.1688},
    "OIL001": {"category_encoded":3,"brand_encoded":14,"category_mean_sales":41.31,"brand_mean_sales":51.98,"category_median_sales":38.97,"brand_median_sales":46.65,"product_global_mean":67.2,"product_global_std":19.58,"product_global_max":178.4,"product_global_median":62.88,"promo_response_rate":1.2242},
    "OIL029": {"category_encoded":3,"brand_encoded":4,"category_mean_sales":41.31,"brand_mean_sales":31.48,"category_median_sales":38.97,"brand_median_sales":28.98,"product_global_mean":15.85,"product_global_std":3.85,"product_global_max":28.98,"product_global_median":14.99,"promo_response_rate":1.1397},
    "OIL032": {"category_encoded":3,"brand_encoded":4,"category_mean_sales":41.31,"brand_mean_sales":31.48,"category_median_sales":38.97,"brand_median_sales":28.98,"product_global_mean":47.13,"product_global_std":11.51,"product_global_max":88.34,"product_global_median":44.87,"promo_response_rate":1.1686},
    "OIL102": {"category_encoded":3,"brand_encoded":14,"category_mean_sales":41.31,"brand_mean_sales":51.98,"category_median_sales":38.97,"brand_median_sales":46.65,"product_global_mean":43.21,"product_global_std":10.72,"product_global_max":78.99,"product_global_median":40.88,"promo_response_rate":1.1315},
    "OIL105": {"category_encoded":3,"brand_encoded":1,"category_mean_sales":41.31,"brand_mean_sales":33.14,"category_median_sales":38.97,"brand_median_sales":31.44,"product_global_mean":33.14,"product_global_std":7.98,"product_global_max":61.34,"product_global_median":31.44,"promo_response_rate":1.1536},
    "RIC002": {"category_encoded":4,"brand_encoded":10,"category_mean_sales":96.43,"brand_mean_sales":123.33,"category_median_sales":75.05,"brand_median_sales":122.23,"product_global_mean":133.99,"product_global_std":32.8,"product_global_max":249.27,"product_global_median":128.06,"promo_response_rate":1.1981},
    "RIC023": {"category_encoded":4,"brand_encoded":10,"category_mean_sales":96.43,"brand_mean_sales":123.33,"category_median_sales":75.05,"brand_median_sales":122.23,"product_global_mean":166.64,"product_global_std":40.06,"product_global_max":298.81,"product_global_median":158.83,"promo_response_rate":1.1427},
    "RIC074": {"category_encoded":4,"brand_encoded":12,"category_mean_sales":96.43,"brand_mean_sales":55.56,"category_median_sales":75.05,"brand_median_sales":52.5,"product_global_mean":55.56,"product_global_std":13.77,"product_global_max":104.33,"product_global_median":52.5,"promo_response_rate":1.1212},
    "RIC085": {"category_encoded":4,"brand_encoded":9,"category_mean_sales":96.43,"brand_mean_sales":56.7,"category_median_sales":75.05,"brand_median_sales":53.45,"product_global_mean":56.7,"product_global_std":14.29,"product_global_max":107.86,"product_global_median":53.45,"promo_response_rate":1.1863},
    "RIC103": {"category_encoded":4,"brand_encoded":10,"category_mean_sales":96.43,"brand_mean_sales":123.33,"category_median_sales":75.05,"brand_median_sales":122.23,"product_global_mean":69.33,"product_global_std":18.03,"product_global_max":151.09,"product_global_median":65.44,"promo_response_rate":1.2074},
    "SUG001": {"category_encoded":5,"brand_encoded":14,"category_mean_sales":45.47,"brand_mean_sales":51.98,"category_median_sales":37.94,"brand_median_sales":46.65,"product_global_mean":85.38,"product_global_std":25.28,"product_global_max":215.9,"product_global_median":79.23,"promo_response_rate":1.2344},
    "SUG030": {"category_encoded":5,"brand_encoded":14,"category_mean_sales":45.47,"brand_mean_sales":51.98,"category_median_sales":37.94,"brand_median_sales":46.65,"product_global_mean":42.31,"product_global_std":11.06,"product_global_max":81.87,"product_global_median":39.46,"promo_response_rate":1.1704},
    "SUG039": {"category_encoded":5,"brand_encoded":14,"category_mean_sales":45.47,"brand_mean_sales":51.98,"category_median_sales":37.94,"brand_median_sales":46.65,"product_global_mean":28.28,"product_global_std":7.14,"product_global_max":51.73,"product_global_median":26.76,"promo_response_rate":1.1198},
    "SUG044": {"category_encoded":5,"brand_encoded":14,"category_mean_sales":45.47,"brand_mean_sales":51.98,"category_median_sales":37.94,"brand_median_sales":46.65,"product_global_mean":49.55,"product_global_std":13.2,"product_global_max":95.16,"product_global_median":46.12,"promo_response_rate":1.257},
    "SUG045": {"category_encoded":5,"brand_encoded":7,"category_mean_sales":45.47,"brand_mean_sales":21.9,"category_median_sales":37.94,"brand_median_sales":20.56,"product_global_mean":21.9,"product_global_std":6.06,"product_global_max":49.68,"product_global_median":20.56,"promo_response_rate":1.2345},
}

DEFAULT_PRODUCT_FEATURES = {
    "category_encoded":0,"brand_encoded":0,
    "category_mean_sales":50.0,"brand_mean_sales":50.0,
    "category_median_sales":45.0,"brand_median_sales":45.0,
    "product_global_mean":50.0,"product_global_std":10.0,
    "product_global_max":100.0,"product_global_median":45.0,
    "promo_response_rate":1.15,
}

# Day-of-week multipliers learned from training data patterns
# Used to add realistic variation to predictions
DOW_PATTERNS = {0:0.92,1:0.94,2:0.95,3:0.95,4:1.10,5:1.35,6:1.26}
MONTH_PATTERNS = {
    1:1.0,2:1.02,3:1.12,4:1.50,5:1.35,6:1.10,
    7:1.02,8:1.05,9:1.10,10:1.05,11:1.02,12:1.22
}


class XGBoostForecaster(BaseForecaster):

    def __init__(self):
        self._model   = None
        self._metrics = {}
        self._load_model()

    def _load_model(self):
        json_path    = os.path.join(MODELS_DIR, "xgboost_v1.json")
        pkl_path     = os.path.join(MODELS_DIR, "xgboost_v1.pkl")
        metrics_path = os.path.join(MODELS_DIR, "model_metrics.json")

        if os.path.exists(json_path):
            self._model = XGBRegressor()
            self._model.load_model(json_path)
        elif os.path.exists(pkl_path):
            with open(pkl_path, "rb") as f:
                self._model = pickle.load(f)
        else:
            raise FileNotFoundError(
                f"No XGBoost model found in {MODELS_DIR}."
            )

        if os.path.exists(metrics_path):
            with open(metrics_path) as f:
                self._metrics = json.load(f).get("xgboost", {})

    def get_model_version(self) -> str:
        return "xgboost_v1"

    def generate_forecast(self, product_code, category, forecast_days,
                          history_df, package_size=1.0, weather_data=None):

        code       = product_code.strip().upper()
        prod_feats = PRODUCT_FEATURES.get(code, DEFAULT_PRODUCT_FEATURES)

        # Get actual recent sales statistics from DB history
        actual_mean, actual_std, recent_values = _get_sales_stats(history_df, prod_feats)

        # Generate predictions using the hybrid approach:
        # 1. Use XGBoost to get relative day patterns (normalized)
        # 2. Scale those patterns to match actual_mean from DB
        results = _hybrid_forecast(
            self._model, prod_feats, actual_mean, actual_std,
            recent_values, forecast_days
        )
        return results

    def calculate_accuracy_metrics(self, history_df):
        return self._metrics if self._metrics else super().calculate_accuracy_metrics(history_df)


def _get_sales_stats(history_df, prod_feats):
    """Extract actual sales statistics from DB history."""
    if history_df.empty or "quantity_sold" not in history_df.columns:
        mean = prod_feats["product_global_mean"]
        std  = prod_feats["product_global_std"]
        return mean, std, np.array([mean] * 30)

    h = history_df.copy()
    h["transaction_date"] = pd.to_datetime(h["transaction_date"])
    h = h.sort_values("transaction_date")
    vals = h["quantity_sold"].values

    # Use recent 90 days for mean (captures current demand level)
    recent = vals[-90:] if len(vals) >= 90 else vals
    mean   = float(np.mean(recent))
    std    = float(np.std(recent)) if len(recent) > 1 else mean * 0.2

    return mean, std, vals


def _hybrid_forecast(model, prod_feats, actual_mean, actual_std,
                     recent_values, forecast_days):
    """
    Hybrid approach:
    - Feed the model normalized features (lag=1.0, rolling_mean=1.0 etc.)
      so it produces RELATIVE pattern predictions independent of scale
    - Then multiply those relative patterns by the actual_mean from DB
    
    This separates "what is the scale" (from actual DB data)
    from "what is the pattern" (from the trained model).
    """
    start = datetime.now().date() + timedelta(days=1)

    # Build feature rows using actual DB sales values as lag/rolling features
    # This ensures each product gets different patterns based on its real sales history
    # We use the actual recent values so the model can distinguish between products

    # Build sales series from history for lag lookups
    sales = pd.Series(dtype=float)
    if not recent_values is None and len(recent_values) > 0:
        sales = pd.Series(recent_values)

    def get_lag(n):
        """Get nth-from-last actual value as lag proxy."""
        pos = min(n, len(recent_values))
        return float(recent_values[-pos]) if pos > 0 else actual_mean

    def get_roll(w, stat="mean"):
        vals = recent_values[-w:] if len(recent_values) >= w else recent_values
        if len(vals) == 0:
            return actual_mean
        if stat == "mean": return float(np.mean(vals))
        if stat == "std":  return float(np.std(vals)) if len(vals)>1 else actual_std
        if stat == "max":  return float(np.max(vals))
        if stat == "min":  return float(np.min(vals))

    rows = []
    for i in range(forecast_days):
        day = start + timedelta(days=i)
        dow = day.weekday()
        doy = day.timetuple().tm_yday
        woy = int(day.isocalendar()[1])
        is_wknd = int(dow >= 5)
        is_hol  = int(day.isoformat() in ALL_PUBLIC_HOLIDAYS)

        l1  = get_lag(1)
        l7  = get_lag(7)
        l14 = get_lag(14)
        l30 = get_lag(30)
        rm7  = get_roll(7)
        rm14 = get_roll(14)
        rm30 = get_roll(30)

        rows.append({
            "day_of_week":        dow,
            "is_weekend":         is_wknd,
            "month":              day.month,
            "quarter":            (day.month - 1) // 3 + 1,
            "day_of_year":        doy,
            "week_of_year":       woy,
            "is_holiday":         is_hol,
            "is_pre_holiday":     0,
            "is_month_start":     int(day.day == 1),
            "is_month_end":       int(day.day >= 28),
            "is_quarter_end":     int(day.month in (3,6,9,12) and day.day >= 28),
            "day_of_week_sin":    math.sin(2*math.pi*dow/7),
            "day_of_week_cos":    math.cos(2*math.pi*dow/7),
            "month_sin":          math.sin(2*math.pi*day.month/12),
            "month_cos":          math.cos(2*math.pi*day.month/12),
            "day_of_year_sin":    math.sin(2*math.pi*doy/365),
            "day_of_year_cos":    math.cos(2*math.pi*doy/365),
            # Real lag/rolling values from actual DB history
            "lag_1":  l1, "lag_7": l7, "lag_14": l14, "lag_30": l30,
            "lag_diff_1_7":  l1 - l7,
            "lag_diff_7_30": l7 - l30,
            "rolling_7_mean":  rm7,
            "rolling_14_mean": rm14,
            "rolling_30_mean": rm30,
            "rolling_7_std":   get_roll(7,"std"),
            "rolling_7_max":   get_roll(7,"max"),
            "rolling_7_min":   get_roll(7,"min"),
            "trend_7_30":      rm7 - rm30,
            "expanding_mean":  actual_mean,
            "is_promotion":0,"lag_1_x_promo":0,"promo_x_holiday":0,
            "promo_x_weekend":0,"promo_x_pre_holiday":0,
            "days_since_promo":30,
            "promo_response_rate":prod_feats["promo_response_rate"],
            "category_encoded":      prod_feats["category_encoded"],
            "brand_encoded":         prod_feats["brand_encoded"],
            "category_mean_sales":   prod_feats["category_mean_sales"],
            "brand_mean_sales":      prod_feats["brand_mean_sales"],
            "category_median_sales": prod_feats["category_median_sales"],
            "brand_median_sales":    prod_feats["brand_median_sales"],
            "product_global_mean":   prod_feats["product_global_mean"],
            "product_global_std":    prod_feats["product_global_std"],
            "product_global_max":    prod_feats["product_global_max"],
            "product_global_median": prod_feats["product_global_median"],
            "qty_vs_category_avg":   actual_mean / max(prod_feats["category_mean_sales"],1),
            "qty_vs_brand_avg":      actual_mean / max(prod_feats["brand_mean_sales"],1),
            "qty_vs_product_avg":    1.0,
        })

    X            = pd.DataFrame(rows)[FEATURE_COLS].values
    raw_preds    = model.predict(X)
    raw_mean     = float(np.mean(raw_preds))

    # If model gives usable relative predictions, use them as multipliers
    # Otherwise fall back to statistical pattern
    results = []
    for i, (raw, row_dict) in enumerate(zip(raw_preds, rows)):
        day     = start + timedelta(days=i)
        dow     = day.weekday()
        is_hol  = row_dict["is_holiday"]

        if raw_mean > 0.01 and not np.isnan(raw) and not np.isinf(raw):
            # Scale raw prediction relative to its own mean, then multiply by actual_mean
            relative = float(raw) / raw_mean
            # Cap relative to reasonable range (0.7x to 1.8x mean)
            relative = max(0.7, min(relative, 1.8))
            predicted = actual_mean * relative
        else:
            # Model produced unusable values — use statistical pattern directly
            dow_mult  = DOW_PATTERNS.get(dow, 1.0)
            mon_mult  = MONTH_PATTERNS.get(day.month, 1.0)
            hol_mult  = 1.5 if is_hol else 1.0
            predicted = actual_mean * dow_mult * (mon_mult ** 0.3) * hol_mult

        predicted = max(1.0, round(float(predicted), 1))

        results.append({
            "date":       day.isoformat(),
            "predicted":  predicted,
            "confidence": round(max(0.70, 0.95 - i*0.01), 3),
            "is_weekend": dow >= 5,
            "is_holiday": bool(is_hol),
        })

    return results