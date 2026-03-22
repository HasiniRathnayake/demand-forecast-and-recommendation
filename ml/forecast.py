"""
forecast.py — Prophet time-series demand forecasting
Project: 2026-Y2-S2-KU-AI-02

Runs Prophet on individual SKUs that have enough data (>= MIN_DATA_POINTS).
For SKUs with insufficient data, falls back to avg_daily_qty_norm × horizon.
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# Soft import: Prophet is optional (system still works without it)
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    print("WARNING: prophet not installed -- using linear extrapolation fallback.")

MIN_DATA_POINTS = 14   # Minimum distinct sales days required for Prophet
FORECAST_HORIZON = 30  # Days to forecast ahead


def run_prophet_for_sku(daily_series: pd.DataFrame) -> float:
    """
    Fit Prophet on a single SKU's daily sales and return the
    forecasted total demand for the next FORECAST_HORIZON days.

    Parameters
    ----------
    daily_series : DataFrame with columns ['date_parsed', 'Quantity']

    Returns
    -------
    float — total predicted demand over next FORECAST_HORIZON days
    """
    prophet_df = daily_series.rename(columns={"date_parsed": "ds", "Quantity": "y"})
    prophet_df = prophet_df[["ds", "y"]].copy()
    prophet_df["y"] = prophet_df["y"].clip(lower=0)

    model = Prophet(
        yearly_seasonality  = False,   # Not enough data for yearly patterns
        weekly_seasonality  = True,
        daily_seasonality   = False,
        changepoint_prior_scale = 0.3,
        seasonality_prior_scale = 10,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(prophet_df)

    future  = model.make_future_dataframe(periods=FORECAST_HORIZON)
    forecast = model.predict(future)
    next_period = forecast.tail(FORECAST_HORIZON)
    total_demand = max(0.0, float(next_period["yhat"].clip(lower=0).sum()))
    return total_demand


def run_forecasts(sales_rows: list[dict], feature_df: pd.DataFrame) -> dict:
    """
    Run demand forecasting for all SKUs and return a dict:
      product_code → forecasted_30day_demand

    SKUs with < MIN_DATA_POINTS sales days use avg_daily_qty_norm × 30.
    """
    if not sales_rows:
        return {}

    sales_df = pd.DataFrame(sales_rows)
    sales_df["Quantity"]    = pd.to_numeric(sales_df.get("Quantity", 0), errors="coerce").fillna(0)
    sales_df["date_parsed"] = pd.to_datetime(sales_df["Date"].astype(str), format="%Y%m%d", errors="coerce")
    sales_df = sales_df.dropna(subset=["date_parsed"])

    daily = sales_df.groupby(["Product_Code", "date_parsed"])["Quantity"].sum().reset_index()

    forecasts = {}
    sku_list = feature_df["product_code"].tolist()
    n_prophet = 0

    for code in sku_list:
        sku_daily = daily[daily["Product_Code"] == code].copy()
        n_days = sku_daily["date_parsed"].nunique()

        row = feature_df[feature_df["product_code"] == code]
        fallback = float(row["avg_daily_qty_norm"].values[0]) * FORECAST_HORIZON if len(row) else 0.0

        if PROPHET_AVAILABLE and n_days >= MIN_DATA_POINTS:
            try:
                forecasts[code] = run_prophet_for_sku(sku_daily)
                n_prophet += 1
            except Exception as e:
                forecasts[code] = fallback
        else:
            forecasts[code] = fallback

    print(f"\n🔮 Forecasting complete: {n_prophet} SKUs used Prophet, {len(sku_list)-n_prophet} used linear fallback.")
    return forecasts
