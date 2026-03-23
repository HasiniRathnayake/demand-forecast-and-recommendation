

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


def _make_sales_rows(n=60):
    dates = [(datetime.now().date() - timedelta(days=i)).isoformat() for i in range(n, 0, -1)]
    qty = np.random.randint(30, 80, size=n).tolist()
    return [{"transaction_date": d, "quantity_sold": q, "is_promotion": False} for d, q in zip(dates, qty)]


MOCK_PRODUCT = {
    "product_code": "RICE001",
    "product_name": "Basmati Rice",
    "category": "Rice",
    "sub_category": "Basmati",
    "unit_price": 250.00,
    "package_size": 5.0,
    "unit_of_measure": "kg",
    "is_ai_supported": True,
    "is_perishable": False,
}

MOCK_WEATHER = {
    "temp_c": 29.5,
    "condition": "partly cloudy",
    "humidity": 72,
    "wind_kph": 12.0,
    "city": "Kandy",
    "available": True,
}


class TestForecastServiceIntegration:
    """Test run_forecast() with mocked DB and weather."""

    @patch("services.forecast_service.get_kandy_weather", return_value=MOCK_WEATHER)
    @patch("services.forecast_service.save_forecast", return_value=True)
    @patch("services.forecast_service.fetch_product_sales", return_value=_make_sales_rows(60))
    def test_run_forecast_returns_three_items(self, mock_sales, mock_save, mock_weather):
        from services.forecast_service import run_forecast
        hist_df, forecast_df, metrics = run_forecast(MOCK_PRODUCT, forecast_days=14)
        assert isinstance(hist_df, pd.DataFrame)
        assert isinstance(forecast_df, pd.DataFrame)
        assert isinstance(metrics, dict)

    @patch("services.forecast_service.get_kandy_weather", return_value=MOCK_WEATHER)
    @patch("services.forecast_service.save_forecast", return_value=True)
    @patch("services.forecast_service.fetch_product_sales", return_value=_make_sales_rows(60))
    def test_forecast_df_has_correct_length(self, mock_sales, mock_save, mock_weather):
        from services.forecast_service import run_forecast
        _, forecast_df, _ = run_forecast(MOCK_PRODUCT, forecast_days=14)
        assert len(forecast_df) == 14

    @patch("services.forecast_service.get_kandy_weather", return_value=MOCK_WEATHER)
    @patch("services.forecast_service.save_forecast", return_value=True)
    @patch("services.forecast_service.fetch_product_sales", return_value=_make_sales_rows(60))
    def test_forecast_df_columns(self, mock_sales, mock_save, mock_weather):
        from services.forecast_service import run_forecast
        _, forecast_df, _ = run_forecast(MOCK_PRODUCT, forecast_days=7)
        required = {"date", "predicted", "confidence", "is_weekend", "is_holiday"}
        assert required.issubset(set(forecast_df.columns))

    @patch("services.forecast_service.get_kandy_weather", return_value=MOCK_WEATHER)
    @patch("services.forecast_service.save_forecast", return_value=True)
    @patch("services.forecast_service.fetch_product_sales", return_value=[])
    def test_empty_history_handled_gracefully(self, mock_sales, mock_save, mock_weather):
        from services.forecast_service import run_forecast
        hist_df, forecast_df, metrics = run_forecast(MOCK_PRODUCT, forecast_days=7)
        assert hist_df.empty
        assert len(forecast_df) == 7  # forecast should still work

    @patch("services.forecast_service.get_kandy_weather", return_value={"available": False})
    @patch("services.forecast_service.save_forecast", return_value=True)
    @patch("services.forecast_service.fetch_product_sales", return_value=_make_sales_rows(60))
    def test_no_weather_handled_gracefully(self, mock_sales, mock_save, mock_weather):
        from services.forecast_service import run_forecast
        _, forecast_df, _ = run_forecast(MOCK_PRODUCT, forecast_days=7)
        assert len(forecast_df) == 7

    @patch("services.forecast_service.get_kandy_weather", return_value=MOCK_WEATHER)
    @patch("services.forecast_service.save_forecast", return_value=True)
    @patch("services.forecast_service.fetch_product_sales", return_value=_make_sales_rows(60))
    def test_metrics_keys_present(self, mock_sales, mock_save, mock_weather):
        from services.forecast_service import run_forecast
        _, _, metrics = run_forecast(MOCK_PRODUCT, forecast_days=14)
        assert "mape" in metrics
        assert "rmse" in metrics
        assert "mae" in metrics
        assert "r2_score" in metrics

    @patch("services.forecast_service.get_kandy_weather", return_value=MOCK_WEATHER)
    @patch("services.forecast_service.save_forecast", return_value=True)
    @patch("services.forecast_service.fetch_product_sales", return_value=_make_sales_rows(60))
    def test_active_model_version_is_string(self, mock_sales, mock_save, mock_weather):
        from services.forecast_service import get_active_model_version
        version = get_active_model_version()
        assert isinstance(version, str)
        assert len(version) > 0


"""
tests/test_forecast_service.py
================================
Integration-style tests for the forecast service.
Uses mocking so no live DB or weather API is needed.
"""