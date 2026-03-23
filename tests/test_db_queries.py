"""
tests/test_db_queries.py
=========================
Tests for DB repository functions using mocked Supabase client.
No live DB connection needed.
"""

import pytest
from unittest.mock import patch, MagicMock


# ── product_repository ─────────────────────────────────────────────────────────

class TestProductRepository:

    def _mock_response(self, data):
        mock = MagicMock()
        mock.data = data
        return mock

    @patch("data.product_repository.get_client")
    def test_fetch_returns_list(self, mock_get_client):
        from data.product_repository import fetch_ai_supported_products
        # Clear cache before test
        fetch_ai_supported_products.clear()

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = self._mock_response([
            {"product_code": "RICE001", "product_name": "Basmati Rice", "category": "Rice", "is_ai_supported": True}
        ])
        mock_get_client.return_value = mock_client
        result = fetch_ai_supported_products()
        assert isinstance(result, list)

    @patch("data.product_repository.get_client")
    def test_fetch_returns_empty_on_db_error(self, mock_get_client):
        from data.product_repository import fetch_ai_supported_products
        fetch_ai_supported_products.clear()

        mock_get_client.side_effect = Exception("DB connection failed")
        result = fetch_ai_supported_products()
        assert result == []


# ── Settings validation ────────────────────────────────────────────────────────

class TestSettings:
    """Validate config/settings.py values."""

    def test_supported_categories_not_empty(self):
        from config.settings import SUPPORTED_CATEGORIES
        assert len(SUPPORTED_CATEGORIES) > 0

    def test_forecast_days_bounds(self):
        from config.settings import MIN_FORECAST_DAYS, MAX_FORECAST_DAYS, DEFAULT_FORECAST_DAYS
        assert MIN_FORECAST_DAYS <= DEFAULT_FORECAST_DAYS <= MAX_FORECAST_DAYS

    def test_all_categories_have_base_demand(self):
        from config.settings import SUPPORTED_CATEGORIES, CATEGORY_BASE_DEMAND
        for cat in SUPPORTED_CATEGORIES:
            assert cat in CATEGORY_BASE_DEMAND, f"'{cat}' missing from CATEGORY_BASE_DEMAND"

    def test_holiday_list_format(self):
        from config.settings import ALL_PUBLIC_HOLIDAYS
        import re
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for h in ALL_PUBLIC_HOLIDAYS:
            assert pattern.match(h), f"Invalid date format: {h}"

    def test_weather_coordinates_for_kandy(self):
        from config.settings import WEATHER_LAT, WEATHER_LON
        # Kandy is roughly at 7.29°N, 80.63°E
        assert 7.0 < WEATHER_LAT < 7.6
        assert 80.3 < WEATHER_LON < 81.0


# ── Weather service ────────────────────────────────────────────────────────────

class TestWeatherService:

    @patch("services.weather_service.requests.get")
    def test_returns_default_when_no_api_key(self, mock_get):
        """With empty API key, should return default dict without calling requests."""
        import services.weather_service as ws
        ws.get_kandy_weather.clear()  # clear cache

        original_key = ws.WEATHER_API_KEY
        ws.WEATHER_API_KEY = ""
        result = ws.get_kandy_weather()
        ws.WEATHER_API_KEY = original_key

        assert result["available"] is False
        assert "temp_c" in result
        mock_get.assert_not_called()

    @patch("services.weather_service.requests.get")
    def test_successful_api_response_parsed(self, mock_get):
        import services.weather_service as ws
        ws.get_kandy_weather.clear()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "main": {"temp": 29.5, "feels_like": 31.0, "humidity": 75},
            "weather": [{"description": "light rain", "icon": "10d"}],
            "wind": {"speed": 3.5},
            "name": "Kandy",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        original_key = ws.WEATHER_API_KEY
        ws.WEATHER_API_KEY = "fake_key_for_test"
        result = ws.get_kandy_weather()
        ws.WEATHER_API_KEY = original_key

        assert result["available"] is True
        assert result["temp_c"] == 29.5
        assert result["condition"] == "Light rain"
        assert result["humidity"] == 75