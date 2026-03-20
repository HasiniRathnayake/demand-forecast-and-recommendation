"""
app.py
======
Main entry point for the Sunrise Supermarket Demand Forecasting Dashboard.
Run with:  streamlit run app.py

Architecture:
  app.py  →  ui/components/sidebar.py  (product selection + settings)
          →  services/forecast_service.py  (orchestrates forecast pipeline)
          →  ui/components/forecast_tab.py   (Tab 1)
          →  ui/components/historical_tab.py (Tab 2)
          →  ui/components/data_tab.py       (Tab 3)
"""

import streamlit as st

from config.settings import APP_TITLE, APP_ICON, APP_SUBTITLE
from ui.styles import inject_styles
from ui.components.sidebar import render_sidebar
from ui.components.forecast_tab import render_forecast_tab
from ui.components.historical_tab import render_historical_tab
from ui.components.data_tab import render_data_tab
from services.forecast_service import run_forecast


# ── Page config (must be FIRST Streamlit call) ─────────────────────────────────
st.set_page_config(
    page_title=f"{APP_TITLE} — Demand Forecast",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(f'<p class="main-header">{APP_ICON} {APP_TITLE}</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-header">{APP_SUBTITLE}</p>', unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
selected_product, settings = render_sidebar()

if selected_product is None:
    st.info("👈 Select a product from the sidebar to begin forecasting.")
    st.stop()

# ── Run forecast pipeline ──────────────────────────────────────────────────────
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
        st.error(f"❌ Unexpected error during forecasting: {exc}")
        st.stop()

# ── Product context bar ────────────────────────────────────────────────────────
col_name, col_cat, col_code = st.columns([3, 1, 1])
col_name.markdown(
    f"**{selected_product.get('product_name', '')}**  "
    f"&nbsp;·&nbsp; {selected_product.get('package_size', '')} {selected_product.get('unit_of_measure', 'units')}"
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

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📈 Forecast View",
    "📊 Historical Analysis",
    "📋 Data & Export",
])

with tab1:
    render_forecast_tab(
        hist_df=hist_df,
        forecast_df=forecast_df,
        metrics=metrics,
        product=selected_product,
        show_confidence=settings["show_confidence"],
        show_weather_impact=settings["show_weather_impact"],
    )

with tab2:
    render_historical_tab(hist_df=hist_df, product=selected_product)

with tab3:
    render_data_tab(hist_df=hist_df, forecast_df=forecast_df, product=selected_product)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="footer">
        Sunrise Supermarket · AI-Powered Demand Forecasting System<br>
        IT2021 AIML Project — Group 2026-Y2-S2-KU-AI-02 &nbsp;|&nbsp;
        Progress 2 &nbsp;|&nbsp; SLIIT Faculty of Computing
    </div>
    """,
    unsafe_allow_html=True,
)