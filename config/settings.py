"""
config/settings.py
==================
App-wide constants, category config, weather config, and model settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Supabase ───────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# ── Weather ────────────────────────────────────────────────────────────────────
WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "")
WEATHER_CITY: str = "Kandy"
WEATHER_COUNTRY: str = "LK"
WEATHER_LAT: float = 7.2906
WEATHER_LON: float = 80.6337
WEATHER_BASE_URL: str = "https://api.openweathermap.org/data/2.5"

# ── Product categories in scope ────────────────────────────────────────────────
SUPPORTED_CATEGORIES: list[str] = [
    "Sugar", "Rice", "Flour", "Dairy", "Oil", "Beverages"
]

# ── Forecasting defaults ───────────────────────────────────────────────────────
DEFAULT_HISTORY_DAYS: int = 90
DEFAULT_FORECAST_DAYS: int = 14
MIN_FORECAST_DAYS: int = 7
MAX_FORECAST_DAYS: int = 30

# Seasonal/weather demand multipliers (used by mock model; real model will learn these)
CATEGORY_BASE_DEMAND: dict[str, float] = {
    "Sugar": 45.0,
    "Rice": 80.0,
    "Flour": 35.0,
    "Dairy": 60.0,
    "Oil": 40.0,
    "Beverages": 55.0,
}

CATEGORY_SEASONALITY: dict[str, dict] = {
    "Sugar": {"april": 1.4, "december": 1.3, "hot_weather": 1.1},
    "Rice": {"april": 1.3, "december": 1.2, "rainy_season": 1.05},
    "Flour": {"december": 1.4, "april": 1.2, "baseline": 1.0},
    "Dairy": {"hot_weather": 1.15, "rainy_season": 0.95, "baseline": 1.0},
    "Oil": {"april": 1.25, "december": 1.2, "baseline": 1.0},
    "Beverages": {"hot_weather": 1.35, "april": 1.3, "december": 1.15},
}

# ── Sri Lanka public holidays (static list – update annually) ──────────────────
SL_PUBLIC_HOLIDAYS_2025: list[str] = [
    "2025-01-01", "2025-01-14", "2025-02-04", "2025-02-12",
    "2025-02-26", "2025-03-13", "2025-04-04", "2025-04-13",
    "2025-04-14", "2025-04-18", "2025-05-01", "2025-05-12",
    "2025-06-10", "2025-07-10", "2025-08-08", "2025-09-05",
    "2025-10-02", "2025-10-20", "2025-11-04", "2025-12-25",
]

SL_PUBLIC_HOLIDAYS_2026: list[str] = [
    "2026-01-01", "2026-01-14", "2026-02-04", "2026-02-19",
    "2026-03-03", "2026-03-31", "2026-04-02", "2026-04-13",
    "2026-04-14", "2026-05-01", "2026-05-31", "2026-06-29",
    "2026-07-29", "2026-08-27", "2026-09-24", "2026-10-09",
    "2026-11-23", "2026-12-25",
]

ALL_PUBLIC_HOLIDAYS: list[str] = SL_PUBLIC_HOLIDAYS_2025 + SL_PUBLIC_HOLIDAYS_2026

# ── Model versioning ───────────────────────────────────────────────────────────
CURRENT_MODEL_VERSION: str = "mock_v1"
# When real models are trained, change to "xgboost_v1" or "rf_v1"

# ── UI ─────────────────────────────────────────────────────────────────────────
APP_TITLE: str = "Sunrise Supermarket"
APP_SUBTITLE: str = "AI-Powered Demand Forecasting Dashboard"
APP_ICON: str = "📊"