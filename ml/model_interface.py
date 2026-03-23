
from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd


class BaseForecaster(ABC):
    """All forecasters must implement these two methods."""

    @abstractmethod
    def generate_forecast(
        self,
        product_code: str,
        category: str,
        forecast_days: int,
        history_df: pd.DataFrame,
        package_size: float = 1.0,
        weather_data: dict | None = None,
    ) -> list[dict]:
        """
        Generate a forecast.

        Returns a list of dicts, one per day:
        {
            "date": "YYYY-MM-DD",
            "predicted": float,       # units to order
            "confidence": float,      # 0.0 – 1.0
            "is_weekend": bool,
            "is_holiday": bool,
        }
        """
        ...

    @abstractmethod
    def get_model_version(self) -> str:
        """Return a short identifier string, e.g. 'mock_v1', 'xgboost_v1'."""
        ...

    def calculate_accuracy_metrics(self, history_df: pd.DataFrame) -> dict:
        """
        Default accuracy calculation from historical data.
        Subclasses may override for model-specific metrics.
        """
        import numpy as np

        if history_df.empty or "quantity_sold" not in history_df.columns:
            return {"mape": 0.0, "rmse": 0.0, "mae": 0.0, "r2_score": 0.0}

        sales = history_df["quantity_sold"].dropna().values
        if len(sales) < 2:
            return {"mape": 0.0, "rmse": 0.0, "mae": 0.0, "r2_score": 0.0}

        mean_sales = np.mean(sales)
        std_sales = np.std(sales)

        # Simulate forecast errors using rolling-mean residuals
        rolling_mean = pd.Series(sales).rolling(7, min_periods=1).mean().values
        errors = sales - rolling_mean
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors**2)))
        with np.errstate(divide="ignore", invalid="ignore"):
            mape_vals = np.where(sales != 0, np.abs(errors / sales), 0)
        mape = float(np.mean(mape_vals) * 100)

        ss_res = np.sum(errors**2)
        ss_tot = np.sum((sales - mean_sales) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot != 0 else 0.0
        r2 = max(0.0, min(1.0, r2))

        return {
            "mape": round(mape, 2),
            "rmse": round(rmse, 2),
            "mae": round(mae, 2),
            "r2_score": round(r2, 4),
        }
    

"""
ml/model_interface.py
======================
Abstract base class for all forecasting models.
Both the mock model (Progress 2) and the real XGBoost/RF models (Progress 3)
must implement this interface.  The service layer only ever talks to this interface,
so swapping mock → real requires changing ONE import in services/forecast_service.py.

To add a real model:
1. Create ml/xgboost_forecaster.py (or rf_forecaster.py)
2. Subclass BaseForecaster and implement generate_forecast() and get_model_version()
3. In services/forecast_service.py change the import line
"""
