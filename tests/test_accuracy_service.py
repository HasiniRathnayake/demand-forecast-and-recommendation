"""
tests/test_accuracy_service.py
================================
Unit tests for services/accuracy_service.py
"""

import pytest
import pandas as pd
import numpy as np
from services.accuracy_service import (
    calculate_metrics,
    accuracy_grade,
    compare_models,
    meets_production_threshold,
)


def _make_df(n=60, low=20, high=80):
    return pd.DataFrame({"quantity_sold": np.random.randint(low, high, n)})


# ── calculate_metrics ──────────────────────────────────────────────────────────

class TestCalculateMetrics:

    def test_returns_all_keys(self):
        metrics = calculate_metrics(_make_df())
        assert {"mape", "rmse", "mae", "r2_score"}.issubset(metrics.keys())

    def test_empty_df_returns_zeros(self):
        metrics = calculate_metrics(pd.DataFrame())
        assert metrics == {"mape": 0.0, "rmse": 0.0, "mae": 0.0, "r2_score": 0.0}

    def test_none_returns_zeros(self):
        metrics = calculate_metrics(None)
        assert metrics["r2_score"] == 0.0

    def test_r2_in_range(self):
        metrics = calculate_metrics(_make_df(90))
        assert 0.0 <= metrics["r2_score"] <= 1.0

    def test_non_negative_errors(self):
        metrics = calculate_metrics(_make_df(60))
        assert metrics["mae"]  >= 0
        assert metrics["rmse"] >= 0
        assert metrics["mape"] >= 0

    def test_missing_column_raises(self):
        bad_df = pd.DataFrame({"wrong_col": [1, 2, 3]})
        with pytest.raises(ValueError, match="quantity_sold"):
            calculate_metrics(bad_df)

    def test_single_row_returns_zeros(self):
        df = pd.DataFrame({"quantity_sold": [42]})
        metrics = calculate_metrics(df)
        assert metrics["r2_score"] == 0.0

    def test_constant_series_handled(self):
        """All identical values — std=0, should not crash."""
        df = pd.DataFrame({"quantity_sold": [50] * 60})
        metrics = calculate_metrics(df)
        assert isinstance(metrics["r2_score"], float)


# ── accuracy_grade ─────────────────────────────────────────────────────────────

class TestAccuracyGrade:

    def test_excellent_grade(self):
        result = accuracy_grade({"mape": 5.0, "rmse": 1.0, "mae": 0.8, "r2_score": 0.92})
        assert result["grade"] == "Excellent"
        assert result["grade_emoji"] == "🟢"

    def test_good_grade(self):
        result = accuracy_grade({"mape": 15.0, "rmse": 3.0, "mae": 2.5, "r2_score": 0.75})
        assert result["grade"] == "Good"

    def test_fair_grade(self):
        result = accuracy_grade({"mape": 28.0, "rmse": 5.0, "mae": 4.0, "r2_score": 0.55})
        assert result["grade"] == "Fair"

    def test_poor_grade(self):
        result = accuracy_grade({"mape": 60.0, "rmse": 10.0, "mae": 8.0, "r2_score": 0.20})
        assert result["grade"] == "Poor"
        assert result["grade_emoji"] == "🔴"

    def test_original_metrics_preserved(self):
        base = {"mape": 8.0, "rmse": 2.0, "mae": 1.5, "r2_score": 0.88}
        result = accuracy_grade(base)
        for k, v in base.items():
            assert result[k] == v

    def test_grade_color_is_hex(self):
        result = accuracy_grade({"mape": 5.0, "rmse": 1.0, "mae": 0.8, "r2_score": 0.91})
        assert result["grade_color"].startswith("#")


# ── compare_models ─────────────────────────────────────────────────────────────

class TestCompareModels:

    def _good(self):
        return {"mape": 8.0, "rmse": 2.0, "mae": 1.5, "r2_score": 0.88}

    def _poor(self):
        return {"mape": 35.0, "rmse": 7.0, "mae": 5.5, "r2_score": 0.45}

    def test_winner_key_present(self):
        result = compare_models(self._good(), self._poor(), "XGBoost", "RF")
        assert "winner" in result

    def test_better_model_wins(self):
        result = compare_models(self._good(), self._poor(), "XGBoost", "RF")
        assert result["winner"] == "XGBoost"

    def test_summary_is_string(self):
        result = compare_models(self._good(), self._poor())
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_delta_r2_correct(self):
        result = compare_models(self._good(), self._poor(), "A", "B")
        expected = round(self._good()["r2_score"] - self._poor()["r2_score"], 4)
        assert result["delta_r2"] == expected

    def test_both_models_graded(self):
        result = compare_models(self._good(), self._poor(), "XGBoost", "RF")
        assert "grade" in result["XGBoost"]
        assert "grade" in result["RF"]


# ── meets_production_threshold ────────────────────────────────────────────────

class TestMeetsProductionThreshold:

    def test_passing_metrics(self):
        passes, msg = meets_production_threshold({"r2_score": 0.80, "mape": 12.0})
        assert passes is True
        assert "✅" in msg

    def test_failing_r2(self):
        passes, msg = meets_production_threshold({"r2_score": 0.50, "mape": 10.0})
        assert passes is False
        assert "❌" in msg
        assert "R²" in msg

    def test_failing_mape(self):
        passes, msg = meets_production_threshold({"r2_score": 0.80, "mape": 30.0})
        assert passes is False
        assert "MAPE" in msg

    def test_both_failing(self):
        passes, msg = meets_production_threshold({"r2_score": 0.30, "mape": 50.0})
        assert passes is False

    def test_exactly_at_threshold(self):
        passes, _ = meets_production_threshold({"r2_score": 0.65, "mape": 25.0})
        assert passes is True