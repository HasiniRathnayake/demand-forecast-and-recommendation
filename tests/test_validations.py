"""
tests/test_validations.py
==========================
Unit tests for input validation logic in the data and service layers.
Run with:  pytest tests/ -v
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta


# ── forecast_repository validation tests ──────────────────────────────────────

class TestFetchProductSalesValidation:
    """Tests for data/forecast_repository.fetch_product_sales validation."""

    def test_empty_product_code_raises(self):
        from data.forecast_repository import fetch_product_sales
        with pytest.raises(ValueError, match="non-empty string"):
            fetch_product_sales("", days=30)

    def test_none_product_code_raises(self):
        from data.forecast_repository import fetch_product_sales
        with pytest.raises((ValueError, TypeError)):
            fetch_product_sales(None, days=30)

    def test_days_zero_raises(self):
        from data.forecast_repository import fetch_product_sales
        with pytest.raises(ValueError, match="between 1 and 730"):
            fetch_product_sales("PROD001", days=0)

    def test_days_negative_raises(self):
        from data.forecast_repository import fetch_product_sales
        with pytest.raises(ValueError, match="between 1 and 730"):
            fetch_product_sales("PROD001", days=-10)

    def test_days_too_large_raises(self):
        from data.forecast_repository import fetch_product_sales
        with pytest.raises(ValueError, match="between 1 and 730"):
            fetch_product_sales("PROD001", days=999)

    def test_valid_inputs_pass(self):
        """Valid inputs should not raise even if DB is unavailable."""
        from data.forecast_repository import fetch_product_sales
        # Should not raise ValueError — may raise other exceptions if DB unavailable
        try:
            fetch_product_sales("PROD001", days=30)
        except ValueError:
            pytest.fail("Valid inputs raised ValueError unexpectedly.")
        except Exception:
            pass  # DB connection errors are acceptable in unit tests


class TestSaveForecastValidation:
    """Tests for data/forecast_repository.save_forecast validation."""

    def _valid_rows(self):
        return [{"date": "2026-04-01", "predicted": 50.0, "confidence": 0.85}]

    def _valid_metrics(self):
        return {"mape": 5.2, "rmse": 3.1, "mae": 2.4, "r2_score": 0.87}

    def test_empty_product_code_raises(self):
        from data.forecast_repository import save_forecast
        with pytest.raises(ValueError, match="non-empty string"):
            save_forecast("", self._valid_rows(), self._valid_metrics(), "mock_v1")

    def test_negative_predicted_raises(self):
        from data.forecast_repository import save_forecast
        bad_rows = [{"date": "2026-04-01", "predicted": -5.0, "confidence": 0.85}]
        with pytest.raises(ValueError, match="non-negative"):
            save_forecast("PROD001", bad_rows, self._valid_metrics(), "mock_v1")

    def test_confidence_above_one_raises(self):
        from data.forecast_repository import save_forecast
        bad_rows = [{"date": "2026-04-01", "predicted": 50.0, "confidence": 1.5}]
        with pytest.raises(ValueError, match="confidence"):
            save_forecast("PROD001", bad_rows, self._valid_metrics(), "mock_v1")

    def test_confidence_below_zero_raises(self):
        from data.forecast_repository import save_forecast
        bad_rows = [{"date": "2026-04-01", "predicted": 50.0, "confidence": -0.1}]
        with pytest.raises(ValueError, match="confidence"):
            save_forecast("PROD001", bad_rows, self._valid_metrics(), "mock_v1")

    def test_missing_required_key_raises(self):
        from data.forecast_repository import save_forecast
        bad_rows = [{"date": "2026-04-01", "predicted": 50.0}]  # missing confidence
        with pytest.raises(ValueError, match="missing keys"):
            save_forecast("PROD001", bad_rows, self._valid_metrics(), "mock_v1")

    def test_empty_rows_returns_true(self):
        """Empty forecast list is a no-op, not an error."""
        from data.forecast_repository import save_forecast
        result = save_forecast("PROD001", [], self._valid_metrics(), "mock_v1")
        assert result is True


# ── MockForecaster tests ───────────────────────────────────────────────────────

class TestMockForecaster:
    """Tests for ml/mock_forecaster.MockForecaster."""

    def _make_history_df(self, n=60):
        import numpy as np
        dates = [datetime.now().date() - timedelta(days=i) for i in range(n, 0, -1)]
        qty = np.random.randint(30, 80, size=n)
        return pd.DataFrame({"transaction_date": dates, "quantity_sold": qty})

    def test_returns_correct_number_of_rows(self):
        from ml.mock_forecaster import MockForecaster
        model = MockForecaster()
        hist_df = self._make_history_df()
        result = model.generate_forecast("P001", "Rice", 14, hist_df)
        assert len(result) == 14

    def test_all_required_keys_present(self):
        from ml.mock_forecaster import MockForecaster
        model = MockForecaster()
        hist_df = self._make_history_df()
        result = model.generate_forecast("P001", "Beverages", 7, hist_df)
        required = {"date", "predicted", "confidence", "is_weekend", "is_holiday"}
        for row in result:
            assert required.issubset(row.keys()), f"Missing keys in row: {row}"

    def test_predicted_is_positive(self):
        from ml.mock_forecaster import MockForecaster
        model = MockForecaster()
        hist_df = self._make_history_df()
        result = model.generate_forecast("P001", "Sugar", 14, hist_df)
        for row in result:
            assert row["predicted"] > 0, f"Non-positive prediction: {row}"

    def test_confidence_in_range(self):
        from ml.mock_forecaster import MockForecaster
        model = MockForecaster()
        hist_df = self._make_history_df()
        result = model.generate_forecast("P001", "Dairy", 14, hist_df)
        for row in result:
            assert 0.0 <= row["confidence"] <= 1.0, f"Out-of-range confidence: {row}"

    def test_model_version_string(self):
        from ml.mock_forecaster import MockForecaster
        model = MockForecaster()
        assert isinstance(model.get_model_version(), str)
        assert len(model.get_model_version()) > 0

    def test_empty_history_still_works(self):
        from ml.mock_forecaster import MockForecaster
        model = MockForecaster()
        empty = pd.DataFrame()
        result = model.generate_forecast("P001", "Oil", 7, empty)
        assert len(result) == 7

    def test_forecast_days_boundary_7(self):
        from ml.mock_forecaster import MockForecaster
        model = MockForecaster()
        result = model.generate_forecast("P001", "Flour", 7, pd.DataFrame())
        assert len(result) == 7

    def test_forecast_days_boundary_30(self):
        from ml.mock_forecaster import MockForecaster
        model = MockForecaster()
        result = model.generate_forecast("P001", "Flour", 30, pd.DataFrame())
        assert len(result) == 30


# ── Accuracy metrics tests ─────────────────────────────────────────────────────

class TestAccuracyMetrics:
    """Tests for BaseForecaster.calculate_accuracy_metrics."""

    def test_returns_all_required_keys(self):
        from ml.mock_forecaster import MockForecaster
        import numpy as np
        model = MockForecaster()
        df = pd.DataFrame({
            "quantity_sold": np.random.randint(20, 60, 60)
        })
        metrics = model.calculate_accuracy_metrics(df)
        assert "mape" in metrics
        assert "rmse" in metrics
        assert "mae" in metrics
        assert "r2_score" in metrics

    def test_r2_score_in_range(self):
        from ml.mock_forecaster import MockForecaster
        import numpy as np
        model = MockForecaster()
        df = pd.DataFrame({"quantity_sold": np.random.randint(20, 60, 60)})
        metrics = model.calculate_accuracy_metrics(df)
        assert 0.0 <= metrics["r2_score"] <= 1.0

    def test_empty_df_returns_zeros(self):
        from ml.mock_forecaster import MockForecaster
        model = MockForecaster()
        metrics = model.calculate_accuracy_metrics(pd.DataFrame())
        assert metrics["r2_score"] == 0.0
        assert metrics["mape"] == 0.0

    def test_non_negative_errors(self):
        from ml.mock_forecaster import MockForecaster
        import numpy as np
        model = MockForecaster()
        df = pd.DataFrame({"quantity_sold": np.random.randint(10, 80, 90)})
        metrics = model.calculate_accuracy_metrics(df)
        assert metrics["mae"] >= 0
        assert metrics["rmse"] >= 0
        assert metrics["mape"] >= 0


# ── Feature engineering tests ──────────────────────────────────────────────────

class TestFeatureEngineering:
    """Tests for ml/feature_engineering.build_features."""

    def _make_sales_df(self, n=60):
        import numpy as np
        dates = pd.date_range(end=datetime.now().date(), periods=n)
        return pd.DataFrame({
            "transaction_date": dates,
            "quantity_sold": np.random.randint(20, 80, n),
            "is_promotion": [False] * n,
        })

    def test_output_has_expected_columns(self):
        from ml.feature_engineering import build_features, get_feature_names
        df = self._make_sales_df(60)
        features = build_features(df)
        expected = set(get_feature_names())
        assert expected.issubset(set(features.columns))

    def test_no_nan_in_features(self):
        from ml.feature_engineering import build_features
        df = self._make_sales_df(60)
        features = build_features(df)
        assert not features.isnull().any().any(), "NaN values found in feature matrix"

    def test_is_weekend_binary(self):
        from ml.feature_engineering import build_features
        df = self._make_sales_df(60)
        features = build_features(df)
        assert set(features["is_weekend"].unique()).issubset({0, 1})

    def test_month_range(self):
        from ml.feature_engineering import build_features
        df = self._make_sales_df(60)
        features = build_features(df)
        assert features["month"].between(1, 12).all()