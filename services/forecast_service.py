"""
services/forecast_service.py
=============================
Orchestrates the full forecasting pipeline:
  1. Load sales history from DB
  2. Fetch weather data
  3. Run the active model
  4. Calculate accuracy metrics
  5. Save forecast back to DB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TO SWAP MOCK → REAL MODEL (Progress 3):
  Change the ONE import line below marked with 🔄
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations
import pandas as pd

# 🔄 Swapping this import when real model is ready:
from ml.mock_forecaster import MockForecaster as ActiveModel
# from ml.xgboost_forecaster import XGBoostForecaster as ActiveModel
# from ml.rf_forecaster import RFForecaster as ActiveModel

from data.forecast_repository import fetch_product_sales, save_forecast
from services.weather_service import get_kandy_weather
from services.accuracy_service import calculate_metrics, accuracy_grade
from config.settings import DEFAULT_HISTORY_DAYS, DEFAULT_FORECAST_DAYS


_model = ActiveModel()


def run_forecast(
    product: dict,
    forecast_days: int = DEFAULT_FORECAST_DAYS,
    history_days: int = DEFAULT_HISTORY_DAYS,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Full forecasting pipeline for a selected product.

    Parameters
    ----------
    product       : dict from product_catalog row
    forecast_days : how many days ahead to forecast
    history_days  : how many days of history to load

    Returns
    -------
    hist_df       : historical sales DataFrame
    forecast_df   : forecast DataFrame
    metrics       : accuracy metrics dict
    """
    code = product.get("product_code", "")
    category = product.get("category", "")
    package_size = float(product.get("package_size") or 1.0)

    # 1 — Load history
    raw = fetch_product_sales(code, history_days)
    hist_df = pd.DataFrame(raw)
    if not hist_df.empty:
        hist_df["transaction_date"] = pd.to_datetime(hist_df["transaction_date"])

    # 2 — Weather
    weather = get_kandy_weather()

    # 3 — Generate forecast
    forecast_rows = _model.generate_forecast(
        product_code=code,
        category=category,
        forecast_days=forecast_days,
        history_df=hist_df,
        package_size=package_size,
        weather_data=weather,
    )
    forecast_df = pd.DataFrame(forecast_rows)
    if not forecast_df.empty:
        forecast_df["date"] = pd.to_datetime(forecast_df["date"])

    # 4 — Accuracy metrics + grade
    raw_metrics = calculate_metrics(hist_df)
    metrics = accuracy_grade(raw_metrics)  # adds grade, grade_color, grade_emoji

    # 5 — Persist to DB (fire-and-forget; errors surfaced inside save_forecast)
    save_forecast(code, forecast_rows, raw_metrics, _model.get_model_version())

    return hist_df, forecast_df, metrics


def get_active_model_version() -> str:
    return _model.get_model_version()