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

# ── Imports ───────────────────────────────────────────────────────────────────
from ui.styles            import inject_styles
from ui.sidebar           import render_sidebar
from pages.dashboard      import show_dashboard
from pages.waste_records  import show_waste_records
from pages.ai_performance import show_ai_performance_comparison, show_ai_performance_analytics
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

    user     = st.session_state.get("user", {}) or {}
    username = user.get("username", "User").capitalize()

    start, end = render_sidebar()

    # ── Top header ────────────────────────────────────────────────────────────
    col_hub, col_title, col_spacer, col_logout = st.columns([1, 4, 3, 1])

    with col_hub:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Hub", key="hub_btn"):
            st.session_state.current_page = "main_dashboard"
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

    with col_logout:
        st.markdown(
            f'<div style="text-align:center;color:#374151;font-size:0.82rem;'
            f'font-weight:500;margin-bottom:0.3rem;">👤 {username}</div>',
            unsafe_allow_html=True,
        )
        if st.button("Logout", key="wpm_logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.markdown("---")

    # ── 5 Main Tabs ───────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "🗑️ Waste Records",
        "🤖 Comparisons & Records",
        "📈 AI Performance",
        "💰 Savings Report",
    ])

    with tab1:
        show_dashboard(start, end)

    with tab2:
        show_waste_records(start, end)

    with tab3:
        show_ai_performance_comparison(start, end)

    with tab4:
        show_ai_performance_analytics(start, end)

    with tab5:
        show_savings_report()