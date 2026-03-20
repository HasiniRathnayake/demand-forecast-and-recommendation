"""
pages/main_dashboard.py
========================
Main dashboard hub shown after login.
Staff see all module cards. Customers see loyalty view.
"""

from __future__ import annotations
import streamlit as st
from ui.styles import inject_styles
from services.auth_service import require_auth, get_current_user, get_user_role, logout


def render_main_dashboard() -> None:
    inject_styles()
    require_auth()

    user = get_current_user()
    role = get_user_role()
    username = user.get("username", "User").capitalize() if user else "User"

    # ── Top nav ────────────────────────────────────────────────────────────────
    col_title, col_spacer, col_user, col_logout = st.columns([4, 2, 1, 1])
    with col_title:
        st.markdown(
            '<p class="main-header" style="margin-bottom:0">🛒 Sunrise Supermarket</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="sub-header" style="margin-top:0">AI Management System</p>',
            unsafe_allow_html=True,
        )
    with col_user:
        role_color = {"admin": "#DC2626", "staff": "#059669", "customer": "#2563EB"}.get(role, "#64748B")
        st.markdown(
            f'<div style="text-align:right;padding-top:.5rem">'
            f'<div style="font-weight:600">👤 {username}</div>'
            f'<div style="font-size:.75rem;color:{role_color};font-weight:600">'
            f'{role.upper()}</div></div>',
            unsafe_allow_html=True,
        )
    with col_logout:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Logout", key="main_logout", type="secondary"):
            logout()

    st.markdown("---")

    # ── Staff / Admin view ─────────────────────────────────────────────────────
    if role in ("staff", "admin"):
        st.markdown(
            f'<div class="section-title">👋 Welcome back, {username}! '
            f'Select a module to get started.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")

        modules = [
            {
                "icon": "📊",
                "title": "Demand Forecast",
                "desc": "AI-powered demand forecasting for key product categories. "
                        "View predictions, historical trends, and override forecasts.",
                "page": "demand_forecast",
                "color": "#2563EB",
                "ready": True,
            },
            {
                "icon": "♻️",
                "title": "Waste & Performance Monitor",
                "desc": "Track product waste, expiry rates, and performance KPIs "
                        "across categories.",
                "page": "waste_monitor",
                "color": "#059669",
                "ready": False,
            },
            {
                "icon": "📦",
                "title": "Stock Replenishment",
                "desc": "Automated stock replenishment suggestions based on "
                        "demand forecasts and current inventory.",
                "page": "stock_replenishment",
                "color": "#7C3AED",
                "ready": False,
            },
            {
                "icon": "🚚",
                "title": "Short-Shipment Detector",
                "desc": "Detect and flag delivery shortfalls against purchase "
                        "orders automatically.",
                "page": "short_shipment",
                "color": "#DC2626",
                "ready": False,
            },
            {
                "icon": "🏪",
                "title": "Smart Inventory Intake",
                "desc": "Streamline goods receiving, verify deliveries, and "
                        "update inventory on arrival.",
                "page": "inventory_intake",
                "color": "#D97706",
                "ready": False,
            },
            {
                "icon": "🎁",
                "title": "Smart Loyalty & Promotions",
                "desc": "Personalised loyalty rewards and promotion management "
                        "for customers.",
                "page": "loyalty",
                "color": "#0891B2",
                "ready": False,
            },
        ]

        cols = st.columns(3)
        for i, mod in enumerate(modules):
            with cols[i % 3]:
                st.markdown(
                    f"""
                    <div class="metric-card" style="min-height:170px;
                         border-left:4px solid {mod['color']};margin-bottom:.75rem">
                        <div style="font-size:1.8rem">{mod['icon']}</div>
                        <div style="font-weight:700;font-size:.95rem;
                             margin:.35rem 0 .2rem">{mod['title']}</div>
                        <div style="font-size:.78rem;color:var(--text-muted,#888);
                             line-height:1.4">{mod['desc']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if mod["ready"]:
                    if st.button(
                        f"Open {mod['title']} →",
                        key=f"nav_{mod['page']}",
                        use_container_width=True,
                        type="primary",
                    ):
                        st.session_state.current_page = mod["page"]
                        st.rerun()
                else:
                    st.button(
                        "Coming Soon",
                        key=f"nav_{mod['page']}",
                        use_container_width=True,
                        disabled=True,
                    )

    # ── Customer view ──────────────────────────────────────────────────────────
    elif role == "customer":
        st.markdown(f"### 👋 Welcome, {username}!")
        st.markdown(
            '<div class="alert-info">Your loyalty dashboard is coming soon.</div>',
            unsafe_allow_html=True,
        )

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="footer">Sunrise Supermarket AI System · '
        'IT2021 AIML Project · Group 2026-Y2-S2-KU-AI-02 · SLIIT</div>',
        unsafe_allow_html=True,
    )