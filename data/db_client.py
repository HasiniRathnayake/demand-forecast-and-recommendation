"""
data/db_client.py
=================
Supabase client singleton.  Import `get_client()` wherever DB access is needed.
Raises a clear RuntimeError if credentials are missing so the app fails fast
with an actionable message instead of a cryptic traceback.
"""

from __future__ import annotations
import streamlit as st
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY


@st.cache_resource(show_spinner=False)
def get_client() -> Client:
    """Return a cached Supabase client.  Called once per Streamlit session."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "❌  Supabase credentials not found.\n"
            "Create a .env file with SUPABASE_URL and SUPABASE_KEY.\n"
            "See README.md for details."
        )
<<<<<<< HEAD
    return create_client(SUPABASE_URL, SUPABASE_KEY)
=======
    return create_client(SUPABASE_URL, SUPABASE_KEY)
>>>>>>> origin/main
