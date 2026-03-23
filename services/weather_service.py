"""
services/weather_service.py
============================
Fetches current weather for Kandy, Sri Lanka from OpenWeatherMap.
Returns a normalised dict consumed by the forecasting service.

If the API key is missing or the call fails, returns safe default values
so the dashboard continues to work without weather data.
"""

from __future__ import annotations
import requests
import streamlit as st
from config.settings import (
    WEATHER_API_KEY,
    WEATHER_LAT,
    WEATHER_LON,
    WEATHER_BASE_URL,
    WEATHER_CITY,
)


@st.cache_data(ttl=1800, show_spinner=False)  # Cache 30 minutes
def get_kandy_weather() -> dict:
    """
    Fetch current weather for Kandy.

    Returns dict:
    {
        "temp_c": float,
        "feels_like_c": float,
        "humidity": int,
        "condition": str,          # e.g. "light rain"
        "icon_url": str,
        "wind_kph": float,
        "city": str,
        "available": bool,         # False if API unavailable
    }
    """
    default = {
        "temp_c": 28.0,
        "feels_like_c": 30.0,
        "humidity": 75,
        "condition": "partly cloudy",
        "icon_url": "",
        "wind_kph": 10.0,
        "city": WEATHER_CITY,
        "available": False,
    }

    if not WEATHER_API_KEY:
        return default  # No key — return defaults silently

    try:
        url = f"{WEATHER_BASE_URL}/weather"
        params = {
            "lat": WEATHER_LAT,
            "lon": WEATHER_LON,
            "appid": WEATHER_API_KEY,
            "units": "metric",
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        icon_code = data["weather"][0].get("icon", "")
        return {
            "temp_c": round(data["main"]["temp"], 1),
            "feels_like_c": round(data["main"]["feels_like"], 1),
            "humidity": data["main"]["humidity"],
            "condition": data["weather"][0].get("description", "").capitalize(),
            "icon_url": f"https://openweathermap.org/img/wn/{icon_code}@2x.png" if icon_code else "",
            "wind_kph": round(data["wind"].get("speed", 0) * 3.6, 1),
            "city": data.get("name", WEATHER_CITY),
            "available": True,
        }
    except requests.Timeout:
        st.warning("⚠️ Weather API timed out. Using default weather values.")
        return default
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            st.warning("⚠️ Invalid Weather API key. Check your .env file.")
        return default
    except Exception:
        return default  # Don't crash the dashboard for weather failures