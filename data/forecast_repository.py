"""
data/forecast_repository.py
============================
Database queries for daily_sales_history and demand_forecasts tables.

demand_forecasts schema (run SQL migration if columns missing):
  forecast_id         uuid / bigint  PK
  product_code        text
  forecast_date       date
  predicted_demand    numeric        ← AI forecast OR override value
  original_ai_demand  numeric        ← original AI value (only set on overrides)
  confidence_level    numeric
  model_version       text
  model_accuracy      jsonb
  is_manual_override  boolean        DEFAULT false
  override_reason     text           ← reason text (only set on overrides)
  override_notes      text           ← staff notes (only set on overrides)
  created_at          timestamptz
"""

from __future__ import annotations
from datetime import datetime, timedelta

import streamlit as st

from data.db_client import get_client
from config.settings import DEFAULT_HISTORY_DAYS


@st.cache_data(ttl=60, show_spinner=False)
def fetch_product_sales(product_code: str, days: int = DEFAULT_HISTORY_DAYS) -> list[dict]:
    """Fetch sales rows for `product_code` covering the last `days` days."""
    if not product_code or not isinstance(product_code, str):
        raise ValueError("product_code must be a non-empty string.")
    product_code = product_code.strip().upper()
    if not (1 <= days <= 730):
        raise ValueError(f"days must be between 1 and 730, got {days}.")

    try:
        client = get_client()
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        response = (
            client.table("daily_sales_history")
            .select("*")
            .eq("product_code", product_code)
            .gte("transaction_date", start_date.isoformat())
            .lte("transaction_date", end_date.isoformat())
            .order("transaction_date")
            .execute()
        )
        return response.data or []
    except ValueError:
        raise
    except Exception as exc:
        st.error(f"⚠️  Could not load sales history: {exc}")
        return []


def fetch_overrides(product_code: str) -> list[dict]:
    """
    Fetch all manual override rows for a product from demand_forecasts.
    Returns list of dicts with keys: forecast_date, predicted_demand,
    original_ai_demand, override_reason, override_notes, created_at.
    """
    if not product_code or not isinstance(product_code, str):
        return []
    try:
        client = get_client()
        response = (
            client.table("demand_forecasts")
            .select(
                "forecast_date, predicted_demand, original_ai_demand, "
                "override_reason, override_notes, created_at, model_version"
            )
            .eq("product_code", product_code)
            .eq("is_manual_override", True)
            .order("forecast_date")
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def save_forecast(
    product_code: str,
    forecast_rows: list[dict],
    accuracy_metrics: dict,
    model_version: str,
    is_manual_override: bool = False,
    original_ai_demand: float | None = None,
    override_reason: str = "",
    override_notes: str = "",
) -> bool:
    """
    Save forecast rows to demand_forecasts table.

    For AI forecasts  (is_manual_override=False):
        Upserts — updates existing AI row for same date, inserts if new.
        Never touches manual override rows.

    For manual overrides (is_manual_override=True):
        Always inserts a NEW row.
        Stores original_ai_demand so the original AI value is never lost.
        Stores override_reason and override_notes for audit trail.
    """
    if not product_code or not isinstance(product_code, str):
        raise ValueError("product_code must be a non-empty string.")
    if not forecast_rows:
        return True

    required_keys = {"date", "predicted", "confidence"}
    for i, row in enumerate(forecast_rows):
        missing = required_keys - row.keys()
        if missing:
            raise ValueError(f"Forecast row {i} is missing keys: {missing}")
        if not isinstance(row["predicted"], (int, float)) or row["predicted"] < 0:
            raise ValueError(f"Row {i}: predicted must be a non-negative number.")
        if not (0.0 <= float(row["confidence"]) <= 1.0):
            raise ValueError(f"Row {i}: confidence must be between 0 and 1.")

    try:
        client = get_client()
        for row in forecast_rows:
            record = {
                "product_code": product_code,
                "forecast_date": row["date"],
                "predicted_demand": round(float(row["predicted"]), 2),
                "confidence_level": round(float(row["confidence"]), 4),
                "model_version": model_version,
                "model_accuracy": accuracy_metrics,
                "created_at": datetime.now().isoformat(),
                "is_manual_override": is_manual_override,
            }

            if is_manual_override:
                # Store original AI value and override metadata
                if original_ai_demand is not None:
                    record["original_ai_demand"] = round(float(original_ai_demand), 2)
                if override_reason:
                    record["override_reason"] = override_reason
                if override_notes:
                    record["override_notes"] = override_notes
                # Always insert — never overwrite existing rows
                client.table("demand_forecasts").insert(record).execute()

            else:
                # AI forecast upsert — only touches non-override rows
                existing = (
                    client.table("demand_forecasts")
                    .select("forecast_id")
                    .eq("product_code", product_code)
                    .eq("forecast_date", row["date"])
                    .eq("is_manual_override", False)
                    .execute()
                )
                if existing.data:
                    client.table("demand_forecasts").update(record).eq(
                        "product_code", product_code
                    ).eq("forecast_date", row["date"]).eq(
                        "is_manual_override", False
                    ).execute()
                else:
                    client.table("demand_forecasts").insert(record).execute()

        return True
    except ValueError:
        raise
    except Exception as exc:
        st.error(f"⚠️  Could not save forecast: {exc}")
        return False