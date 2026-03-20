from __future__ import annotations
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from ml.model_interface import BaseForecaster
from config.settings import (
    ALL_PUBLIC_HOLIDAYS,
    CATEGORY_BASE_DEMAND,
    CATEGORY_SEASONALITY,
)


class MockForecaster(BaseForecaster):
    """Heuristic mock model – no training required."""

    def get_model_version(self) -> str:
        return "mock_v1"

    def generate_forecast(
        self,
        product_code: str,
        category: str,
        forecast_days: int,
        history_df: pd.DataFrame,
        package_size: float = 1.0,
        weather_data: dict | None = None,
    ) -> list[dict]:
        """Generate forecast rows for the next `forecast_days` days."""

        base = CATEGORY_BASE_DEMAND.get(category, 50.0)
        seasonality = CATEGORY_SEASONALITY.get(category, {})

        # Derive a base from recent history if available
        if not history_df.empty and "quantity_sold" in history_df.columns:
            recent = history_df.tail(30)["quantity_sold"]
            if len(recent) > 0:
                base = float(recent.mean())

        # Weather factor
        weather_factor = self._weather_factor(weather_data, category)

        results = []
        start_date = datetime.now().date() + timedelta(days=1)

        for i in range(forecast_days):
            day = start_date + timedelta(days=i)
            is_weekend = day.weekday() >= 5
            is_holiday = day.isoformat() in ALL_PUBLIC_HOLIDAYS

            # Seasonal month factor
            month_factor = self._month_factor(day.month, seasonality)
            dow_factor = 1.25 if is_weekend else 1.0
            holiday_factor = 1.5 if is_holiday else 1.0

            predicted = (
                base
                * month_factor
                * dow_factor
                * holiday_factor
                * weather_factor
                * (1 + random.uniform(-0.05, 0.05))  # ±5% noise
            )

            # Adjust for package size (never predict less than 1 unit)
            predicted = max(1.0, round(predicted / max(package_size, 1.0), 1))

            # Confidence: higher near-term, lower long-term
            confidence = max(0.70, 0.95 - (i * 0.01))

            results.append(
                {
                    "date": day.isoformat(),
                    "predicted": predicted,
                    "confidence": round(confidence, 3),
                    "is_weekend": is_weekend,
                    "is_holiday": is_holiday,
                }
            )

        return results

    # ── private helpers ────────────────────────────────────────────────────────

    def _month_factor(self, month: int, seasonality: dict) -> float:
        """Map calendar month to a rough demand multiplier."""
        if month == 4:
            return seasonality.get("april", 1.0)
        if month == 12:
            return seasonality.get("december", 1.0)
        return seasonality.get("baseline", 1.0)

    def _weather_factor(self, weather_data: dict | None, category: str) -> float:
        """Adjust demand based on current Kandy weather."""
        if not weather_data:
            return 1.0
        temp = weather_data.get("temp_c", 27.0)
        condition = weather_data.get("condition", "").lower()
        seasonality = CATEGORY_SEASONALITY.get(category, {})

        factor = 1.0
        if temp > 30:
            factor *= seasonality.get("hot_weather", 1.0)
        if "rain" in condition or "drizzle" in condition:
            factor *= seasonality.get("rainy_season", 1.0)
        return factor
    
"""
ml/mock_forecaster.py
======================
Mock forecaster for Progress 1 & 2.
Uses heuristic rules (day-of-week, public holidays, weather, seasonality)
to generate realistic-looking demand numbers WITHOUT a trained model.

Replacing with XGBoostForecaster or RFForecaster for Progress 3.
"""