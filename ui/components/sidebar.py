"""
ui/components/sidebar.py
=========================
Sidebar rendering: category filter, product selector, product details,
weather widget, and forecast settings.
Returns the selected product dict and forecast settings.
"""

from __future__ import annotations
import streamlit as st

from data.product_repository import fetch_ai_supported_products, fetch_all_categories
from services.weather_service import get_kandy_weather
from config.settings import (
    MIN_FORECAST_DAYS,
    MAX_FORECAST_DAYS,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_HISTORY_DAYS,
    APP_ICON,
    SUPPORTED_CATEGORIES,
)


def render_sidebar() -> tuple[dict | None, dict]:
    """
    Render the full sidebar.

    Returns
    -------
    selected_product : dict | None
    settings         : {"forecast_days": int, "history_days": int,
                        "show_confidence": bool, "show_weather_impact": bool}
    """
    with st.sidebar:
        # ── Header ────────────────────────────────────────────────────────────
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:1rem;">
              <span style="font-size:1.8rem">{APP_ICON}</span>
              <div>
                <div style="font-weight:700;font-size:1rem;line-height:1.2">Sunrise Supermarket</div>
                <div style="font-size:.72rem;color:var(--text-muted,#888)">Demand Forecasting</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Weather widget ─────────────────────────────────────────────────────
        _render_weather_widget()

        st.markdown("---")

        # ── Product selection ──────────────────────────────────────────────────
        st.markdown("**🛒 Product Selection**")

        products = fetch_ai_supported_products()
        if not products:
            st.error("No AI-supported products found.\nPlease check the database.")
            return None, _default_settings()

        categories = fetch_all_categories() or SUPPORTED_CATEGORIES
        selected_category = st.selectbox(
            "Category",
            ["All Categories"] + categories,
            key="sb_category",
        )

        filtered = (
            [p for p in products if p.get("category") == selected_category]
            if selected_category != "All Categories"
            else products
        )

        if not filtered:
            st.warning(f"No products found in '{selected_category}'.")
            return None, _default_settings()

        # Build display map
        product_map: dict[str, dict] = {}
        for p in filtered:
            pkg = (
                f" · {p.get('package_size')} {p.get('unit_of_measure','units')}"
                if p.get("package_size")
                else ""
            )
            label = f"{p['product_name']}{pkg}  ({p['product_code']})"
            product_map[label] = p

        selected_label = st.selectbox("Product", list(product_map.keys()), key="sb_product")
        selected_product = product_map[selected_label]

        # ── Product info ───────────────────────────────────────────────────────
        st.markdown("---")
        _render_product_info(selected_product)

        # ── Forecast settings ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**⚙️ Forecast Settings**")

        forecast_days = st.slider(
            "Forecast Period (days)",
            min_value=MIN_FORECAST_DAYS,
            max_value=MAX_FORECAST_DAYS,
            value=DEFAULT_FORECAST_DAYS,
            step=7,
            key="sb_forecast_days",
            help="How many days ahead to forecast demand.",
        )
        history_days = st.select_slider(
            "History Window (days)",
            options=[90, 180, 365, 500, 730],
            value=730,
            key="sb_history_days",
            help="How many past days of sales data to use for forecasting.",
        )
        show_confidence = st.toggle("Show Confidence Interval", value=True, key="sb_conf")
        show_weather = st.toggle("Show Weather Impact", value=True, key="sb_weather")

        settings = {
            "forecast_days": forecast_days,
            "history_days": history_days,
            "show_confidence": show_confidence,
            "show_weather_impact": show_weather,
        }

        return selected_product, settings


# ── private helpers ────────────────────────────────────────────────────────────

def _render_weather_widget() -> None:
    weather = get_kandy_weather()
    if not weather.get("available"):
        st.markdown(
            '<div class="alert-info" style="font-size:.78rem">🌤 Weather API not connected.<br>Add WEATHER_API_KEY to .env</div>',
            unsafe_allow_html=True,
        )
        return

    icon_html = (
        f'<img src="{weather["icon_url"]}" style="width:40px;height:40px;vertical-align:middle">'
        if weather.get("icon_url")
        else "🌤"
    )
    st.markdown(
        f"""
        <div class="weather-card">
          <div class="weather-label">📍 {weather["city"]}, Sri Lanka</div>
          <div style="display:flex;align-items:center;gap:.5rem;margin:.3rem 0">
            {icon_html}
            <span class="weather-temp">{weather["temp_c"]}°C</span>
          </div>
          <div class="weather-detail">{weather["condition"]}</div>
          <div class="weather-detail" style="margin-top:.3rem">
            💧 {weather["humidity"]}%  &nbsp;|&nbsp;  💨 {weather["wind_kph"]} km/h
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_product_info(product: dict) -> None:
    is_ai = product.get("is_ai_supported", False)
    is_perishable = product.get("is_perishable", False)
    offer = product.get("offer_price")

    badges = ""
    if is_ai:
        badges += '<span class="badge badge-ai">🤖 AI Supported</span> '
    if is_perishable:
        badges += '<span class="badge badge-holiday">⏱ Perishable</span>'

    if badges:
        st.markdown(badges, unsafe_allow_html=True)
        st.markdown("")

    price_line = f"Rs. {product.get('unit_price', 0):.2f}"
    if offer:
        price_line += f"  ~~Rs. {offer:.2f}~~"

    st.markdown(
        f"""
        <div class="product-info-grid">
          <span class="info-label">Category</span>
          <span class="info-value">{product.get('category','—')}</span>
          <span class="info-label">Sub-category</span>
          <span class="info-value">{product.get('sub_category','—')}</span>
          <span class="info-label">Unit Price</span>
          <span class="info-value">Rs. {product.get('unit_price', 0):.2f}</span>
          {"<span class='info-label'>Offer Price</span><span class='info-value'>Rs. " + f"{offer:.2f}" + "</span>" if offer else ""}
          <span class="info-label">Package</span>
          <span class="info-value">{product.get('package_size','—')} {product.get('unit_of_measure','units')}</span>
          {"<span class='info-label'>Shelf Life</span><span class='info-value'>" + str(product.get('shelf_life_days','—')) + " days</span>" if is_perishable else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _default_settings() -> dict:
    return {
        "forecast_days": DEFAULT_FORECAST_DAYS,
        "history_days": DEFAULT_HISTORY_DAYS,
        "show_confidence": True,
        "show_weather_impact": True,
    }