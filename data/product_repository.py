"""
data/product_repository.py
===========================
All database queries related to the product_catalog table.
Returns plain dicts/lists so the service layer stays DB-agnostic.
"""

from __future__ import annotations
import streamlit as st
from data.db_client import get_client
from config.settings import SUPPORTED_CATEGORIES


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ai_supported_products() -> list[dict]:
    """
    Fetch products where is_ai_supported = TRUE AND category is in scope.
    Returns empty list (never raises) – callers handle the empty state.
    """
    try:
        client = get_client()
        response = (
            client.table("product_catalog")
            .select("*")
            .eq("is_ai_supported", True)
            .in_("category", SUPPORTED_CATEGORIES)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        # Surface DB errors visibly in the sidebar but keep the app alive
        import streamlit as st
        st.error(f"⚠️  Could not load products from database: {exc}")
        return []


@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_categories() -> list[str]:
    """Return distinct categories present in the AI-supported product set."""
    products = fetch_ai_supported_products()
    seen: set[str] = set()
    result: list[str] = []
    for p in products:
        cat = p.get("category", "")
        if cat and cat not in seen:
            seen.add(cat)
            result.append(cat)
    return sorted(result)