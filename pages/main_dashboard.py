"""
pages/main_dashboard.py
========================
Main dashboard hub shown after login.
Staff see all module cards. Customers see loyalty view.
"""

from __future__ import annotations
import streamlit as st
from ui.styles import inject_styles, render_page_heading
from services.auth_service import require_auth, get_current_user, get_user_role, logout
def render_main_dashboard() -> None:
    inject_styles()
    # Hide auto-discovered page navigation
    st.markdown("""
        <style>
        [data-testid="stSidebarNav"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)
    require_auth()

    user = get_current_user()
    role = get_user_role()
    username = user.get("username", "User").capitalize() if user else "User"

    # ── Top nav ────────────────────────────────────────────────────────────────
    col_title, col_spacer, col_user, col_logout = st.columns([4, 2, 1, 1])
    with col_title:
        render_page_heading("AI Management System")
    with col_user:
        role_color = {"admin": "#DC2626", "staff": "#059669", "customer": "#2563EB", "supplier": "#7C3AED"}.get(role, "#64748B")
        st.markdown(
            f'<div style="text-align:right;padding-top:.5rem">'
            f'<div style="font-weight:600;font-size:1.02rem">👤 {username}</div>'
            f'<div style="font-size:.95rem;color:{role_color};font-weight:700">'
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
                "ready": True,
            },
            {
                "icon": "📦",
                "title": "Stock Replenishment",
                "desc": "Automated stock replenishment suggestions based on "
                        "demand forecasts and current inventory.",
                "page": "stock_replenishment",
                "color": "#7C3AED",
                "ready": True,
            },
            {
                "icon": "🚚",
                "title": "Short-Shipment Detector",
                "desc": "Detect and flag delivery shortfalls against purchase "
                        "orders automatically.",
                "page": "short_shipment",
                "color": "#DC2626",
                "ready": True,
            },
            {
                "icon": "🎁",
                "title": "Smart Loyalty & Promotions",
                "desc": "Personalised loyalty rewards and promotion management "
                        "for customers.",
                "page": "loyalty",
                "color": "#0891B2",
                "ready": True,
            },
        ]

        if role == "admin":
            modules.append(
                {
                    "icon": "✅",
                    "title": "Staff Approvals",
                    "desc": "Review and approve new staff registrations before they can log in.",
                    "page": "admin_staff_approvals",
                    "color": "#0F766E",
                    "ready": True,
                }
            )

        cols = st.columns(3)
        for i, mod in enumerate(modules):
            with cols[i % 3]:
                st.markdown(
                    f"""
                    <div class="metric-card dashboard-card" style="border-left:4px solid {mod['color']};">
                        <div class="dashboard-card-icon">{mod['icon']}</div>
                        <div class="dashboard-card-title">{mod['title']}</div>
                        <div class="dashboard-card-desc">{mod['desc']}</div>
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
        inject_styles()
        user = get_current_user()
        from pages.customer_dashboard import show_customer_dashboard
        show_customer_dashboard(user.get('customer_id'))

    elif role == "supplier":
    # Auto-redirect to supplier dashboard immediately
        st.session_state.current_page = "supplier_dashboard"
        st.rerun()