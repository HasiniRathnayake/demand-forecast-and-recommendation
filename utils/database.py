"""
utils/database.py
Author : IT24103258
"""

from __future__ import annotations
from datetime import date, datetime
import pandas as pd
import streamlit as st
from supabase import Client


def _parse_dt(val):
    if pd.isna(val) or val is None:
        return None
    try:
        return pd.to_datetime(val)
    except Exception:
        return None


def _get_client() -> Client:
    if "supabase" not in st.session_state:
        st.error(
            "Database connection not found. "
            "Make sure your .env file exists with SUPABASE_URL and SUPABASE_KEY, "
            "then restart the app."
        )
        st.stop()
    return st.session_state["supabase"]


@st.cache_data(ttl=60)
def fetch_waste_records(start: date | None = None, end: date | None = None) -> pd.DataFrame:
    try:
        db = _get_client()
        q = db.table("waste_records").select("*").order("waste_date", desc=True)
        if start:
            q = q.gte("waste_date", start.isoformat())
        if end:
            q = q.lte("waste_date", end.isoformat())
        resp = q.execute()
        if not resp.data:
            return pd.DataFrame()
        df = pd.DataFrame(resp.data)
        df["waste_date"]  = pd.to_datetime(df["waste_date"])
        df["recorded_at"] = df["recorded_at"].apply(_parse_dt)
        return df
    except Exception as exc:
        st.error(f"Error fetching waste records: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def fetch_ai_performance(start: date | None = None, end: date | None = None) -> pd.DataFrame:
    try:
        db = _get_client()
        q = db.table("ai_performance").select("*").order("forecast_date", desc=True)
        if start:
            q = q.gte("forecast_date", start.isoformat())
        if end:
            q = q.lte("forecast_date", end.isoformat())
        resp = q.execute()
        if not resp.data:
            return pd.DataFrame()
        df = pd.DataFrame(resp.data)
        df["forecast_date"] = pd.to_datetime(df["forecast_date"])
        df["evaluated_at"]  = df["evaluated_at"].apply(_parse_dt)
        return df
    except Exception as exc:
        st.error(f"Error fetching AI performance data: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def fetch_demand_forecasts() -> pd.DataFrame:
    try:
        db = _get_client()
        resp = (
            db.table("demand_forecasts")
            .select("forecast_id, product_code, forecast_date, predicted_demand")
            .order("forecast_date", desc=True)
            .execute()
        )
        if not resp.data:
            return pd.DataFrame()
        df = pd.DataFrame(resp.data)
        df["forecast_date"] = pd.to_datetime(df["forecast_date"])
        return df
    except Exception as exc:
        st.error(f"Error fetching demand forecasts: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def product_code_exists(code: str) -> bool:
    try:
        db = _get_client()
        resp = (
            db.table("product_catalog")
            .select("product_code")
            .eq("product_code", code.upper())
            .execute()
        )
        return bool(resp.data)
    except Exception:
        return False


def insert_waste_record(
    product_code: str,
    waste_date: date,
    quantity_wasted: float,
    waste_reason: str,
    estimated_loss: float,
) -> tuple[bool, str]:
    try:
        db = _get_client()
        db.table("waste_records").insert({
            "product_code":    product_code.upper(),
            "waste_date":      waste_date.isoformat(),
            "quantity_wasted": round(quantity_wasted, 3),
            "waste_reason":    waste_reason,
            "estimated_loss":  round(estimated_loss, 2),
        }).execute()
        return True, "Waste record saved successfully."
    except Exception as exc:
        return False, f"Database error: {exc}"


def upsert_ai_comparison(
    forecast_id: str,
    product_code: str,
    forecast_date: date,
    predicted_demand: float,
    actual_sales: float,
) -> tuple[bool, str]:
    try:
        db = _get_client()
        error_value      = actual_sales - predicted_demand
        error_percentage = abs(error_value / predicted_demand * 100) if predicted_demand > 0 else 0.0
        now = datetime.now().isoformat()

        existing = (
            db.table("ai_performance")
            .select("performance_id")
            .eq("forecast_id", forecast_id)
            .execute()
        )

        if existing.data:
            db.table("ai_performance").update({
                "actual_sales":     round(actual_sales, 3),
                "error_value":      round(error_value, 3),
                "error_percentage": round(error_percentage, 2),
                "evaluated_at":     now,
            }).eq("performance_id", existing.data[0]["performance_id"]).execute()
            return True, "Comparison record updated."
        else:
            db.table("ai_performance").insert({
                "forecast_id":      forecast_id,
                "product_code":     product_code,
                "forecast_date":    forecast_date.isoformat(),
                "predicted_demand": round(predicted_demand, 3),
                "actual_sales":     round(actual_sales, 3),
                "error_value":      round(error_value, 3),
                "error_percentage": round(error_percentage, 2),
                "evaluated_at":     now,
            }).execute()
            return True, "Comparison record saved."
    except Exception as exc:
        return False, f"Database error: {exc}"