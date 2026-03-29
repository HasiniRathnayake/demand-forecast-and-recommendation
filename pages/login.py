"""
pages/login.py
==============
Login and Registration page with real-time field validation.
"""

from __future__ import annotations
import re
import streamlit as st
from ui.styles import inject_styles
from services.auth_service import (
    login_user, register_user, init_session,
)


def render_login_page() -> None:
    inject_styles()
    init_session()

    # ── Header ─────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align:center;padding:2rem 0 1rem">
            <div style="font-size:3rem">🛒</div>
            <h1 style="font-size:2rem;font-weight:700;
                color:var(--accent,#2563EB);margin:.3rem 0">
                Sunrise Supermarket
            </h1>
            <p style="color:var(--text-muted,#64748B);font-size:1rem;margin:0">
                AI-Powered Management System
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 2, 1])

    with col_c:
        tab_login, tab_register = st.tabs(["🔑 Login", "📝 Register"])

        # ── LOGIN ──────────────────────────────────────────────────────────────
        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)

            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                key="login_username",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password",
            )

            # Real-time validation feedback
            if username and len(username.strip()) < 3:
                st.markdown(
                    '<div class="alert-info" style="padding:.4rem .8rem;font-size:.8rem">'
                    '⚠️ Username must be at least 3 characters.</div>',
                    unsafe_allow_html=True,
                )
            if password and len(password) < 6:
                st.markdown(
                    '<div class="alert-info" style="padding:.4rem .8rem;font-size:.8rem">'
                    '⚠️ Password must be at least 6 characters.</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<br>", unsafe_allow_html=True)

            # Disable button if fields obviously invalid
            login_ready = (
                len(username.strip()) >= 3 and len(password) >= 6
            ) if username and password else False

            if st.button(
                "Login →",
                type="primary",
                use_container_width=True,
                key="login_btn",
                disabled=not login_ready,
            ):
                with st.spinner("Authenticating..."):
                    success, message, user = login_user(username.strip(), password)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.session_state.current_page = "main_dashboard"
                    st.success(message)
                    st.rerun()
                else:
                    st.markdown(
                        f'<div class="alert-info">{message}</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("---")
            st.caption("Having trouble? Contact your system administrator.")

        # ── REGISTER ───────────────────────────────────────────────────────────
        with tab_register:
            st.markdown("<br>", unsafe_allow_html=True)

            reg_username = st.text_input(
                "Username",
                placeholder="At least 3 characters, letters/numbers only",
                key="reg_username",
            )
            reg_email = st.text_input(
                "Email",
                placeholder="your@email.com",
                key="reg_email",
            )
            reg_role = st.selectbox(
                "Account Type",
                ["staff", "customer", "supplier"],
                key="reg_role",
                help="Staff/admin manage modules. Customers use loyalty. Suppliers use supplier portal.",
                format_func=lambda r: (
                    "👔 Staff" if r == "staff" else
                    "👤 Customer" if r == "customer" else
                    "🏭 Supplier"
                ),
            )
            reg_supplier_id = ""
            if reg_role == "supplier":
                reg_supplier_id = st.text_input(
                    "Supplier ID",
                    placeholder="Enter supplier UUID from suppliers table",
                    key="reg_supplier_id",
                    help="Required for supplier login so we can map orders to this account.",
                )
            reg_password = st.text_input(
                "Password",
                type="password",
                placeholder="Minimum 6 characters",
                key="reg_password",
            )
            reg_confirm = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Repeat your password",
                key="reg_confirm",
            )

            # ── Real-time validation feedback ──────────────────────────────────
            reg_errors: list[str] = []
            reg_ok = True

            if reg_username:
                if len(reg_username.strip()) < 3:
                    reg_errors.append("⚠️ Username must be at least 3 characters.")
                    reg_ok = False
                elif not re.match(r'^[a-zA-Z0-9_\-]+$', reg_username):
                    reg_errors.append("⚠️ Username: letters, numbers, hyphens and underscores only.")
                    reg_ok = False

            if reg_email:
                if not re.match(r'^[^@]+@[^@]+\.[^@]+$', reg_email):
                    reg_errors.append("⚠️ Please enter a valid email address.")
                    reg_ok = False

            if reg_password:
                if len(reg_password) < 6:
                    reg_errors.append("⚠️ Password must be at least 6 characters.")
                    reg_ok = False

            if reg_confirm and reg_password:
                if reg_password != reg_confirm:
                    reg_errors.append("⚠️ Passwords do not match.")
                    reg_ok = False
                elif len(reg_password) >= 6:
                    st.markdown(
                        '<div class="alert-success" style="padding:.4rem .8rem;font-size:.8rem">'
                        '✅ Passwords match.</div>',
                        unsafe_allow_html=True,
                    )

            # Show all errors inline
            for err in reg_errors:
                st.markdown(
                    f'<div class="alert-info" style="padding:.4rem .8rem;font-size:.8rem">'
                    f'{err}</div>',
                    unsafe_allow_html=True,
                )

            # All fields filled and valid?
            all_filled = all([
                reg_username, reg_email, reg_password, reg_confirm
            ])
            if reg_role == "supplier" and not reg_supplier_id.strip():
                reg_ok = False
                reg_errors.append("⚠️ Supplier ID is required for supplier accounts.")

            register_ready = all_filled and reg_ok and not reg_errors

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button(
                "Create Account →",
                type="primary",
                use_container_width=True,
                key="reg_btn",
                disabled=not register_ready,
            ):
                with st.spinner("Creating account..."):
                    success, message = register_user(
                        reg_username,
                        reg_email,
                        reg_password,
                        reg_role,
                        supplier_id=(reg_supplier_id.strip() if reg_role == "supplier" else None),
                    )
                if success:
                    st.success(message)
                    st.info("✅ Account created! Switch to the Login tab to sign in.")
                else:
                    st.markdown(
                        f'<div class="alert-info">{message}</div>',
                        unsafe_allow_html=True,
                    )

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="footer">Sunrise Supermarket AI System · '
        'IT2021 AIML Project · Group 2026-Y2-S2-KU-AI-02 · SLIIT</div>',
        unsafe_allow_html=True,
    )