"""
data/db_client.py
"""
import os
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def get_client():
    if "supabase" not in st.session_state:
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        if not SUPABASE_URL or not SUPABASE_KEY:
            st.error("Supabase credentials not found. Check your .env file.")
            st.stop()
        st.session_state["supabase"] = create_client(SUPABASE_URL, SUPABASE_KEY)
    return st.session_state["supabase"]
