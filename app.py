

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

    with st.spinner(f"Generating forecast for **{selected_product.get('product_name', '')}**..."):
        try:
            hist_df, forecast_df, metrics = run_forecast(
                product=selected_product,
                forecast_days=settings["forecast_days"],
                history_days=settings["history_days"],
            )
        except ValueError as ve:
            st.error(f"❌ Validation error: {ve}")
            st.stop()
        except Exception as exc:
            st.error(f"❌ Unexpected error: {exc}")
            st.stop()

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

    tab1, tab2, tab3 = st.tabs(["📈 Forecast View", "📊 Historical Analysis", "📋 Data & Export"])
    with tab1:
        render_forecast_tab(
            hist_df=hist_df, forecast_df=forecast_df, metrics=metrics,
            product=selected_product,
            show_confidence=settings["show_confidence"],
            show_weather_impact=settings["show_weather_impact"],
        )
    with tab2:
        render_historical_tab(hist_df=hist_df, product=selected_product)
    with tab3:
        render_data_tab(hist_df=hist_df, forecast_df=forecast_df, product=selected_product)

    st.markdown(
        '<div class="footer">Sunrise Supermarket · Demand Forecasting · IT2021 AIML Project · SLIIT</div>',
        unsafe_allow_html=True,
    )

# ── Fallback ───────────────────────────────────────────────────────────────────
else:
    st.session_state.current_page = "login"
    st.rerun()

