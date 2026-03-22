"""
app.py
Author : IT24103258
"""

import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

try:
    st.set_page_config(
        page_title="Waste & Performance Monitor | Sunrise Supermarket",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

# ── Supabase connection ───────────────────────────────────────────────────────
if "supabase" not in st.session_state:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error(
            "### Supabase credentials not found\n\n"
            "Create a `.env` file with:\n\n"
            "```\n"
            "SUPABASE_URL=https://your-project-id.supabase.co\n"
            "SUPABASE_KEY=your-anon-key-here\n"
            "```"
        )
        st.stop()

    try:
        st.session_state["supabase"] = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as exc:
        st.error(f"Failed to connect to Supabase: {exc}")
        st.stop()

# ── Session state defaults ────────────────────────────────────────────────────
if "current_page"  not in st.session_state:
    st.session_state.current_page  = "login"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user"          not in st.session_state:
    st.session_state.user          = None
if "wpm_page"      not in st.session_state:
    st.session_state.wpm_page      = "Dashboard"

# ── Imports ───────────────────────────────────────────────────────────────────
from ui.styles            import inject_styles
from ui.sidebar           import render_sidebar
from pages.dashboard      import show_dashboard
from pages.waste_records  import show_waste_records
from pages.ai_performance import show_ai_performance
from pages.savings_report import show_savings_report

# ── Router ────────────────────────────────────────────────────────────────────
page = st.session_state.current_page

if page == "login":
    from login import render_login_page
    render_login_page()

elif page == "main_dashboard":
    from main_dashboard import render_main_dashboard
    render_main_dashboard()

elif page == "waste_monitor":
    inject_styles()

    user       = st.session_state.get("user", {}) or {}
    username   = user.get("username", "User").capitalize()
    role       = user.get("role", "staff")

    start, end = render_sidebar()
    wpm_page   = st.session_state.get("wpm_page", "Dashboard")

    if wpm_page == "Dashboard":
        # ── Top nav only on Dashboard ─────────────────────────────────────────
        col_hub, col_title, col_spacer, col_user, col_logout = st.columns([1, 4, 2, 1, 1])

        with col_hub:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("← Hub", key="hub_btn"):
                st.session_state.current_page = "main_dashboard"
                st.session_state.wpm_page     = "Dashboard"
                st.rerun()

        with col_title:
            st.markdown(
                """
                <div style="text-align:center;padding-top:0.3rem">
                    <span style="font-size:2.2rem;font-weight:700;color:#2563EB;">
                        📊 Sunrise Supermarket
                    </span><br>
                    <span style="font-size:1.1rem;color:#64748B;">
                        Waste &amp; Performance Monitor
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_spacer:
            pass

        with col_user:
            pass

        with col_logout:
            st.markdown(
                f'<div style="text-align:center;color:#374151;'
                f'font-size:0.82rem;font-weight:500;margin-bottom:0px;'
                f'padding-top:0.4rem;">👤 {username}</div>',
                unsafe_allow_html=True,
            )
            if st.button("Logout", key="wpm_logout", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        st.markdown("---")
        show_dashboard(start, end)

    elif wpm_page == "Waste Records":
        show_waste_records(start, end)

    elif wpm_page == "AI Performance":
        show_ai_performance(start, end)

    elif wpm_page == "Savings Report":
        show_savings_report()
