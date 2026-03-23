"""
data/inventory_intake_repository.py
===================================
Supabase queries for Smart Inventory Intake.
"""

from __future__ import annotations

from data.db_client import get_client


def fetch_suppliers() -> dict[str, int]:
    """Return supplier name -> supplier_id map."""
    try:
        client = get_client()
        res = client.table("suppliers").select("supplier_id, supplier_name").execute()
        rows = res.data or []
        return {row["supplier_name"]: row["supplier_id"] for row in rows if row.get("supplier_name")}
    except Exception:
        return {}


def fetch_ai_products() -> dict[str, str]:
    """Return AI-supported product name -> product_code map."""
    try:
        client = get_client()
        res = (
            client.table("product_catalog")
            .select("product_code, product_name")
            .eq("is_ai_supported", True)
            .execute()
        )
        rows = res.data or []
        return {row["product_name"]: row["product_code"] for row in rows if row.get("product_name")}
    except Exception:
        return {}


def fetch_latest_forecast(product_code: str) -> tuple[int | None, float]:
    """Return (forecast_id, predicted_demand) for latest row by forecast_date."""
    if not product_code:
        return None, 0.0

    try:
        client = get_client()
        res = (
            client.table("demand_forecasts")
            .select("forecast_id, predicted_demand")
            .eq("product_code", product_code)
            .order("forecast_date", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None, 0.0

        latest = rows[0]
        return latest.get("forecast_id"), float(latest.get("predicted_demand") or 0.0)
    except Exception:
        return None, 0.0


def save_intake_log(payload: dict) -> bool:
    """Insert one intake record into inventory_intake_log."""
    try:
        client = get_client()
        client.table("inventory_intake_log").insert(payload).execute()
        return True
    except Exception:
        return False


def fetch_recent_intake_logs(limit: int = 20) -> list[dict]:
    """Fetch recent intake logs with product relation for dashboard analytics."""
    try:
        client = get_client()
        res = (
            client.table("inventory_intake_log")
            .select("created_at, expected_qty, actual_qty, is_anomaly, product_catalog(product_name)")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception:
        return []
