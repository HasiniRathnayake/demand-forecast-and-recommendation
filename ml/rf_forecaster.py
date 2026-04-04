"""
ml/rf_forecaster.py
====================
Real Random Forest forecaster — loads rf_v1.pkl from ml/saved_models/
and implements the BaseForecaster interface.

To activate in services/forecast_service.py change:
    from ml.mock_forecaster import MockForecaster as ActiveModel
    to:
    from ml.rf_forecaster import RFForecaster as ActiveModel
"""

from __future__ import annotations
import os
import json
import pickle

import numpy as np
import pandas as pd

from ml.model_interface import BaseForecaster
from ml.xgboost_forecaster import FEATURE_COLS, MODELS_DIR, _build_feature_rows, _format_results

from config.settings import ALL_PUBLIC_HOLIDAYS


class RFForecaster(BaseForecaster):
    """Real Random Forest demand forecaster using trained model."""

    def __init__(self):
        self._model   = None
        self._metrics = {}
        self._load_model()

    def _load_model(self) -> None:
        pkl_path     = os.path.join(MODELS_DIR, "rf_v1.pkl")
        metrics_path = os.path.join(MODELS_DIR, "model_metrics.json")

        if not os.path.exists(pkl_path):
            raise FileNotFoundError(
                f"Random Forest model not found at {pkl_path}.\n"
                "Train the model on Colab and download to ml/saved_models/"
            )

        with open(pkl_path, "rb") as f:
            self._model = pickle.load(f)

        if os.path.exists(metrics_path):
            with open(metrics_path) as f:
                self._metrics = json.load(f).get("random_forest", {})

    def get_model_version(self) -> str:
        return "rf_v1"

    def generate_forecast(
        self,
        product_code: str,
        category: str,
        forecast_days: int,
        history_df: pd.DataFrame,
        package_size: float = 1.0,
        weather_data: dict | None = None,
    ) -> list[dict]:
        """Generate demand forecast using the trained Random Forest model."""
        if self._model is None:
            raise RuntimeError("Random Forest model is not loaded.")

        from ml.xgboost_forecaster import PRODUCT_FEATURES, DEFAULT_PRODUCT_FEATURES
        prod_feats = PRODUCT_FEATURES.get(
            product_code.strip().upper(),
            DEFAULT_PRODUCT_FEATURES
        )
        feature_rows = _build_feature_rows(history_df, forecast_days, prod_feats)
        if not feature_rows:
            return []

        X = pd.DataFrame(feature_rows)[FEATURE_COLS].values
        predictions = self._model.predict(X)
        return _format_results(predictions, forecast_days)

    def calculate_accuracy_metrics(self, history_df: pd.DataFrame) -> dict:
        if self._metrics:
            return self._metrics
        return super().calculate_accuracy_metrics(history_df)