
import streamlit as st

from config.settings import APP_ICON
from services.auth_service import init_session, is_authenticated, get_user_role

# ── Page config — MUST be first Streamlit call ────────────────────────────────
st.set_page_config(
    page_title="Sunrise Supermarket — AI System",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session init ───────────────────────────────────────────────────────────────
init_session()

page = st.session_state.get("current_page", "login")

# ── Route: not authenticated → login ──────────────────────────────────────────
if not is_authenticated():
    from pages.login import render_login_page
    render_login_page()

# ── Route: main hub ───────────────────────────────────────────────────────────
elif page == "main_dashboard":
    from pages.main_dashboard import render_main_dashboard
    render_main_dashboard()

# ── Route: demand forecast module ─────────────────────────────────────────────
elif page == "demand_forecast":
    from ui.styles import inject_styles
    from ui.components.sidebar import render_sidebar
    from ui.components.forecast_tab import render_forecast_tab
    from ui.components.historical_tab import render_historical_tab
    from ui.components.data_tab import render_data_tab
    from services.forecast_service import run_forecast
    from services.auth_service import get_current_user, logout
    from config.settings import APP_TITLE, APP_SUBTITLE

    inject_styles()

    # Top nav
    col_back, col_title, col_user = st.columns([1, 5, 1])
    with col_back:
        if st.button("← Hub", key="back_to_hub"):
            st.session_state.current_page = "main_dashboard"
            st.rerun()
    with col_title:
        st.markdown(f'<p class="main-header">{APP_ICON} {APP_TITLE}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="sub-header">{APP_SUBTITLE}</p>', unsafe_allow_html=True)
    with col_user:
        user = get_current_user()
        if user:
            st.caption(f"👤 {user.get('username','').capitalize()}")
        if st.button("Logout", key="forecast_logout"):
            logout()

    selected_product, settings = render_sidebar()

    if selected_product is None:
        st.info("👈 Select a product from the sidebar to begin forecasting.")
        st.stop()

    # ── Cache forecast in session state so reruns triggered by input widgets
    # (override form, reason dropdown etc.) don't regenerate new random values
    # which would change current_val and break the same-value validation ────────
    forecast_cache_key = (
        selected_product.get("product_code", ""),
        settings["forecast_days"],
        settings["history_days"],
    )

    if (
        "forecast_cache" not in st.session_state
        or st.session_state.get("forecast_cache_key") != forecast_cache_key
    ):
        with st.spinner(f"Generating forecast for **{selected_product.get('product_name', '')}**..."):
            try:
                hist_df, forecast_df, metrics = run_forecast(
                    product=selected_product,
                    forecast_days=settings["forecast_days"],
                    history_days=settings["history_days"],
                )
                st.session_state.forecast_cache = (hist_df, forecast_df, metrics)
                st.session_state.forecast_cache_key = forecast_cache_key
            except ValueError as ve:
                st.error(f"❌ Validation error: {ve}")
                st.stop()
            except Exception as exc:
                st.error(f"❌ Unexpected error: {exc}")
                st.stop()
    else:
        hist_df, forecast_df, metrics = st.session_state.forecast_cache

    col_name, col_cat, col_code = st.columns([3, 1, 1])
    col_name.markdown(
        f"**{selected_product.get('product_name', '')}**"
        f"&nbsp;·&nbsp;{selected_product.get('package_size','')} {selected_product.get('unit_of_measure','units')}"
    )
    col_cat.markdown(
        f'<span class="badge badge-model">{selected_product.get("category","")}</span>',
        unsafe_allow_html=True,
    )
    col_code.markdown(
        f'<code style="font-size:.8rem">{selected_product.get("product_code","")}</code>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Tab navigation using radio so the selected tab persists across reruns.
    # st.tabs() in Streamlit 1.32 always resets to Tab 1 on rerun — a radio
    # button stored in session_state stays on the correct tab. ─────────────────
    tab_options = ["📈 Forecast View", "📊 Historical Analysis", "📋 Data & Export"]

    selected_tab = st.radio(
        "Navigate",
        tab_options,
        horizontal=True,
        key="forecast_tab_radio",
        label_visibility="collapsed",
    )

    st.markdown("---")

    if selected_tab == "📈 Forecast View":
        render_forecast_tab(
            hist_df=hist_df, forecast_df=forecast_df, metrics=metrics,
            product=selected_product,
            show_confidence=settings["show_confidence"],
            show_weather_impact=settings["show_weather_impact"],
        )
    elif selected_tab == "📊 Historical Analysis":
        render_historical_tab(hist_df=hist_df, product=selected_product)
    elif selected_tab == "📋 Data & Export":
        render_data_tab(hist_df=hist_df, forecast_df=forecast_df, product=selected_product)

    st.markdown(
        '<div class="footer">Sunrise Supermarket · Demand Forecasting · IT2021 AIML Project · SLIIT</div>',
        unsafe_allow_html=True,
    )
# ── Route: customer dashboard ─────────────────────────────────────────────────
elif page == "customer_dashboard":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user, logout, get_user_role
    inject_styles()

    user = get_current_user()
    if not user or user.get('role') != 'customer':
        st.session_state.current_page = "main_dashboard"
        st.rerun()

    if st.button("← Back", key="back_customer"):
        st.session_state.current_page = "main_dashboard"
        st.rerun()

    from pages.customer_dashboard import show_customer_dashboard
    show_customer_dashboard(user.get('customer_id'))

elif page == "supplier_dashboard":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user, logout
    inject_styles()

    user = get_current_user()
    if not user or user.get('role') not in ('supplier', 'admin'):
        st.session_state.current_page = "main_dashboard"
        st.rerun()

    if st.button("← Back", key="back_supplier"):
        st.session_state.current_page = "main_dashboard"
        st.rerun()

    from pages.supplier_dashboard import render_supplier_dashboard
    render_supplier_dashboard()

elif page == "customer_settings":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user
    inject_styles()

    user = get_current_user()
    if not user or user.get('role') != 'customer':
        st.session_state.current_page = "main_dashboard"
        st.rerun()

    if st.button("← Back to Dashboard", key="back_customer_settings"):
        st.session_state.current_page = "customer_dashboard"
        st.rerun()

    from pages.customer_settings import show_customer_settings
    show_customer_settings(user.get('customer_id'))

# ── Route: loyalty module ─────────────────────────────────────────────────────
elif page == "loyalty":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user, logout
    inject_styles()

    col_back, col_title, col_user = st.columns([1, 5, 1])
    with col_back:
        if st.button("← Hub", key="back_loyalty"):
            st.session_state.current_page = "main_dashboard"
            st.rerun()
    with col_title:
        st.markdown(
            '<p class="main-header">🎁 Smart Loyalty & Promotions</p>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<p class="sub-header">Customer segmentation, personalised offers & email campaigns</p>',
            unsafe_allow_html=True
        )
    with col_user:
        user = get_current_user()
        if user:
            st.caption(f"👤 {user.get('username','').capitalize()}")
        if st.button("Logout", key="loyalty_logout"):
            logout()

    st.markdown("---")

    from pages.loyalty_home      import show_home
    from pages.loyalty_segments  import show_segments
    from pages.loyalty_campaigns import show_promotions
    from pages.loyalty_history   import show_email_history

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏠 Overview",
        "👥 Customer Segments",
        "🎯 Campaign Builder",
        "📧 Email History"
    ])
    with tab1:
        show_home()
    with tab2:
        show_segments()
    with tab3:
        show_promotions()
    with tab4:
        show_email_history()

    st.markdown(
        '<div class="footer">Sunrise Supermarket · Smart Loyalty & Promotions · '
        'IT24100971 · SLIIT</div>',
        unsafe_allow_html=True,
    )
# ── Route: short shipment detector ───────────────────────────────────────────
elif page == "short_shipment":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user, logout
    inject_styles()

    col_back, col_title, col_user = st.columns([1, 5, 1])
    with col_back:
        if st.button("← Hub", key="back_shipment"):
            st.session_state.current_page = "main_dashboard"
            st.rerun()
    with col_title:
        st.markdown(
            '<p class="main-header">🚚 Short-Shipment Detector</p>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<p class="sub-header">Detect and flag delivery shortfalls against purchase orders</p>',
            unsafe_allow_html=True
        )
    with col_user:
        user = get_current_user()
        if user:
            st.caption(f"👤 {user.get('username','').capitalize()}")
        if st.button("Logout", key="shipment_logout"):
            logout()

    st.markdown("---")

    from pages.short_shipment_page import render_short_shipment
    def ensure_sample_data():
     """Placeholder for sample data check"""
    # This is called but not defined in your code
     return True
    render_short_shipment()

    st.markdown(
        '<div class="footer">Sunrise Supermarket · Short-Shipment Detector · SLIIT</div>',
        unsafe_allow_html=True,
    )

# ── Route: stock replenishment ────────────────────────────────────────────────
elif page == "stock_replenishment":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user, logout
    inject_styles()

    col_back, col_title, col_user = st.columns([1, 5, 1])
    with col_back:
        if st.button("← Hub", key="back_replenish"):
            st.session_state.current_page = "main_dashboard"
            st.rerun()
    with col_title:
        st.markdown(
            '<p class="main-header">📦 Stock Replenishment</p>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<p class="sub-header">Automated ML stock replenishment suggestions</p>',
            unsafe_allow_html=True
        )
    with col_user:
        user = get_current_user()
        if user:
            st.caption(f"👤 {user.get('username','').capitalize()}")
        if st.button("Logout", key="replenish_logout"):
            logout()

    st.markdown("---")

    from pages.stock_replenishment import render_stock_replenishment
    render_stock_replenishment()

    st.markdown(
        '<div class="footer">Sunrise Supermarket · Stock Replenishment · SLIIT</div>',
        unsafe_allow_html=True,
    )

# ── Route: smart inventory intake ────────────────────────────────────────────
elif page == "inventory_intake":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user, logout
    from pages.inventory_intake_page import render_inventory_intake

    inject_styles()

    col_back, col_title, col_user = st.columns([1, 5, 1])
    with col_back:
        if st.button("← Hub", key="back_inventory"):
            st.session_state.current_page = "main_dashboard"
            st.rerun()
    with col_title:
        st.markdown(
            '<p class="main-header">🏪 Smart Inventory Intake</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="sub-header">AI-assisted receiving validation and anomaly capture</p>',
            unsafe_allow_html=True,
        )
    with col_user:
        user = get_current_user()
        if user:
            st.caption(f"👤 {user.get('username','').capitalize()}")
        if st.button("Logout", key="inventory_logout"):
            logout()

    st.markdown("---")
    render_inventory_intake()

    st.markdown(
        '<div class="footer">Sunrise Supermarket · Smart Inventory Intake · SLIIT</div>',
        unsafe_allow_html=True,
    )

# ── Route: admin staff approvals ─────────────────────────────────────────────
elif page == "admin_staff_approvals":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user, get_user_role, logout
    from pages.admin_staff_approvals import render_admin_staff_approvals

    inject_styles()

    if get_user_role() != "admin":
        st.error("⛔ Access denied. Admin only.")
        st.session_state.current_page = "main_dashboard"
        st.rerun()

    col_back, col_title, col_user = st.columns([1, 5, 1])
    with col_back:
        if st.button("← Hub", key="back_admin_approvals"):
            st.session_state.current_page = "main_dashboard"
            st.rerun()
    with col_title:
        st.markdown(
            '<p class="main-header">🛡️ Admin Controls</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="sub-header">Manage pending staff account approvals</p>',
            unsafe_allow_html=True,
        )
    with col_user:
        user = get_current_user()
        if user:
            st.caption(f"👤 {user.get('username','').capitalize()}")
        if st.button("Logout", key="admin_approval_logout"):
            logout()

    st.markdown("---")
    render_admin_staff_approvals()

    st.markdown(
        '<div class="footer">Sunrise Supermarket · Admin Staff Approvals · SLIIT</div>',
        unsafe_allow_html=True,
    )

# ── Route: waste & performance monitor ───────────────────────────────────────
elif page == "waste_monitor":
    from ui.styles            import inject_styles
    from ui.sidebar           import render_sidebar
    from pages.dashboard      import show_dashboard
    from pages.waste_records  import show_waste_records
    from pages.ai_performance import show_ai_performance_comparison, show_ai_performance_analytics, show_rl_predictions
    from pages.savings_report import show_savings_report
    from services.auth_service import logout

    inject_styles()

    user     = st.session_state.get("user", {}) or {}
    username = user.get("username", "User").capitalize()

    start, end = render_sidebar()

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
            logout()

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard",
        "🗑️ Waste Records",
        "🤖 Comparisons & Records",
        "📈 AI Performance",
        "💰 Savings Report",
        "🧠 RL Performance",
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

    with tab6:
        show_rl_predictions()    

# ── Fallback ───────────────────────────────────────────────────────────────────
else:
    st.session_state.current_page = "login"
    st.rerun()
