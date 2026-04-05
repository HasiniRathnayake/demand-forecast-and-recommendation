"""
data/ai_performance_repository.py
Author: IT24103258

Reads and writes to the ai_performance table (IT24103258's table).
Does NOT touch demand_forecasts — that is the friend's table.
Uses the same get_client() pattern as the rest of the project.
"""

from __future__ import annotations
from datetime import date, datetime
import pandas as pd
import streamlit as st
from data.db_client import get_client


def fetch_rl_performance(start: date, end: date) -> pd.DataFrame:
    """
    Fetches ai_performance rows for the given date range.
    Returns an empty DataFrame if nothing found.
    """
    try:
        client = get_client()
        resp = (
            client.table("ai_performance")
            .select("*")
            .gte("forecast_date", str(start))
            .lte("forecast_date", str(end))
            .order("forecast_date", desc=True)
            .execute()
        )
        if not resp.data:
            return pd.DataFrame()
        df = pd.DataFrame(resp.data)
        if "forecast_date" in df.columns:
            df["forecast_date"] = pd.to_datetime(df["forecast_date"])
        if "evaluated_at" in df.columns:
            df["evaluated_at"] = pd.to_datetime(df["evaluated_at"], errors="coerce")
        return df
    except Exception as e:
        st.error(f"Could not load RL performance data: {e}")
        return pd.DataFrame()


def log_rl_performance(
    forecast_id: str,
    product_code: str,
    forecast_date: date,
    predicted_demand: float,
    actual_sales: float | None = None,
    error_value: float | None = None,
    error_percentage: float | None = None,
) -> tuple[bool, str]:
    """
    Inserts a new row into ai_performance.
    actual_sales can be None — filled in later when real sales arrive.
    """
    try:
        client = get_client()
        data: dict = {
            "forecast_id"      : forecast_id,
            "product_code"     : product_code,
            "forecast_date"    : str(forecast_date),
            "predicted_demand" : predicted_demand,
            "actual_sales"     : actual_sales,
            "error_value"      : error_value,
            "error_percentage" : error_percentage,
            "evaluated_at"     : datetime.utcnow().isoformat(),
        }
        client.table("ai_performance").insert(data).execute()
        return True, "Logged successfully."
    except Exception as e:
        return False, str(e)


def update_rl_actual_sales(
    performance_id: str,
    actual_sales: float,
    predicted_demand: float,
) -> tuple[bool, str]:
    """
    Updates actual_sales, error_value, and error_percentage
    for an existing ai_performance row once real sales are known.
    """
    try:
        client = get_client()
        error_value      = round(abs(predicted_demand - actual_sales), 3)
        error_percentage = (
            round(abs(predicted_demand - actual_sales) / actual_sales * 100, 2)
            if actual_sales != 0 else None
        )
        client.table("ai_performance").update({
            "actual_sales"     : actual_sales,
            "error_value"      : error_value,
            "error_percentage" : error_percentage,
            "evaluated_at"     : datetime.utcnow().isoformat(),
        }).eq("performance_id", performance_id).execute()
        return True, "Updated successfully."
    except Exception as e:
        return False, str(e)