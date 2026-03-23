"""
Data & Export
Sub-tabs:
  1. Historical Data  — paginated table + CSV download
  2. Forecast Data    — forecast table with override indicators + CSV download
  3. Manual Override  — validated form to override AI forecast values
  4. Override History — all past overrides for this product
"""

from __future__ import annotations
from datetime import datetime

import pandas as pd
import streamlit as st

from data.forecast_repository import save_forecast, fetch_overrides
from config.settings import MAX_FORECAST_DAYS


def render_data_tab(
    hist_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    product: dict,
) -> None:
    """Render the Data & Export tab with 4 sub-tabs."""

    sub1, sub2, sub3, sub4 = st.tabs([
        "📋 Historical Data",
        "📅 Forecast Data",
        "✏️ Manual Override",
        "🔁 Override History",
    ])

    with sub1:
        _render_historical_table(hist_df, product)

    with sub2:
        _render_forecast_table(forecast_df, product)

    with sub3:
        _render_manual_override(forecast_df, product)

    with sub4:
        _render_override_history(product)


# ── Historical data ────────────────────────────────────────────────────────────

def _render_historical_table(hist_df: pd.DataFrame, product: dict) -> None:
    st.markdown('<div class="section-title">📋 Recent Historical Sales</div>', unsafe_allow_html=True)

    if hist_df.empty:
        st.info("No historical data available for this product.")
        return

    page_size = 20
    total_rows = len(hist_df)
    total_pages = max(1, -(-total_rows // page_size))

    col_filter, col_page = st.columns([3, 1])
    with col_page:
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, key="hist_page")
    with col_filter:
        filter_promo = st.checkbox("Show promotion days only", value=False, key="hist_promo_filter")

    display = hist_df.copy()
    if filter_promo and "is_promotion" in display.columns:
        display = display[display["is_promotion"] == True]

    start = (page - 1) * page_size
    end = start + page_size
    page_data = display.iloc[start:end]

    st.caption(f"Showing rows {start+1}–{min(end, len(display))} of {len(display)}")

    col_config = {
        "transaction_date": st.column_config.DateColumn("Date"),
        "quantity_sold": st.column_config.NumberColumn("Units Sold", format="%d"),
        "is_promotion": st.column_config.CheckboxColumn("Promotion"),
    }
    display_cols = [c for c in ["transaction_date", "quantity_sold", "is_promotion"] if c in page_data.columns]
    st.dataframe(page_data[display_cols], use_container_width=True, hide_index=True, column_config=col_config)

    csv_hist = hist_df.to_csv(index=False)
    st.download_button(
        "📥 Download Historical Data (CSV)",
        data=csv_hist,
        file_name=f"history_{product.get('product_code','')}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key=f"dl_hist_{product.get('product_code','')}",
    )


# ── Forecast data ──────────────────────────────────────────────────────────────

def _render_forecast_table(forecast_df: pd.DataFrame, product: dict) -> None:
    st.markdown('<div class="section-title">📅 Forecast Data</div>', unsafe_allow_html=True)

    if forecast_df.empty:
        st.info("No forecast data generated yet.")
        return

    # Fetch overrides from DB and merge into display
    overrides = fetch_overrides(product.get("product_code", ""))
    override_map: dict[str, dict] = {}
    for ov in overrides:
        override_map[ov["forecast_date"]] = ov

    display = forecast_df.copy()
    display["date_str"] = display["date"].dt.strftime("%Y-%m-%d")
    display["day_type"] = display.apply(
        lambda r: "🎉 Holiday" if r.is_holiday else "📅 Weekend" if r.is_weekend else "📋 Weekday",
        axis=1,
    )

    rows = []
    for _, r in display.iterrows():
        date_str = r["date_str"]
        ov = override_map.get(date_str)
        if ov:
            rows.append({
                "Date": date_str,
                "Day Type": r["day_type"],
                "AI Forecast": f"{r['predicted']:.1f}",
                "Final Value": f"✏️ {ov['predicted_demand']:.1f}",
                "Confidence": f"{r['confidence']*100:.0f}%",
                "Status": "🔁 Overridden",
                "Override Reason": ov.get("override_reason", "—"),
            })
        else:
            rows.append({
                "Date": date_str,
                "Day Type": r["day_type"],
                "AI Forecast": f"{r['predicted']:.1f}",
                "Final Value": f"{r['predicted']:.1f}",
                "Confidence": f"{r['confidence']*100:.0f}%",
                "Status": "🤖 AI",
                "Override Reason": "—",
            })

    table_df = pd.DataFrame(rows)
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    if override_map:
        st.markdown(
            f'<div class="alert-info">✏️ <strong>{len(override_map)} date(s)</strong> have been manually overridden. '
            f'See the Override History tab for full details.</div>',
            unsafe_allow_html=True,
        )

    csv_fc = table_df.to_csv(index=False)
    st.download_button(
        "📥 Download Forecast (CSV)",
        data=csv_fc,
        file_name=f"forecast_{product.get('product_code','')}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key=f"dl_forecast_{product.get('product_code','')}",
    )


# ── Manual override ────────────────────────────────────────────────────────────

def _render_manual_override(forecast_df: pd.DataFrame, product: dict) -> None:
    """
    Validated form to override AI forecast values.
    - current_val always read from in-memory forecast_df (never DB)
    - Uses session state flag to prevent balloon re-trigger on tab switch
    - Saves original AI value separately so nothing is lost
    """
    st.markdown('<div class="section-title">✏️ Manual Forecast Override</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="alert-info">'
        'Use this form to override the AI-predicted demand for a specific date. '
        'The original AI forecast is preserved — overrides are saved as separate records '
        'and shown in the Forecast Data and Override History tabs.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    if forecast_df.empty:
        st.warning("Generate a forecast first before applying overrides.")
        return

    # ── Initialize session state flags ─────────────────────────────────────────
    # These prevent success message re-firing when switching tabs
    if "override_saved" not in st.session_state:
        st.session_state.override_saved = False
    if "override_saved_for" not in st.session_state:
        st.session_state.override_saved_for = ""

    date_options = forecast_df["date"].dt.strftime("%Y-%m-%d").tolist()

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_date = st.selectbox(
            "Forecast Date", date_options, key="override_date",
        )

    # When date changes, reset saved flag
    if st.session_state.override_saved_for != selected_date:
        st.session_state.override_saved = False
        st.session_state.override_saved_for = selected_date

    # Always read from in-memory forecast_df — NEVER from DB
    current_row = forecast_df[forecast_df["date"].dt.strftime("%Y-%m-%d") == selected_date]
    current_val = float(current_row["predicted"].values[0]) if not current_row.empty else 0.0

    # Reference label above input
    st.markdown(
        f'<div class="alert-info" style="margin-bottom:.5rem">'
        f'🤖 <strong>AI Forecast for {selected_date}:</strong> {current_val:.1f} units — enter your override below'
        f'</div>',
        unsafe_allow_html=True,
    )

    with col2:
        override_val = st.number_input(
            "Override Value (units)",
            min_value=0.0,
            max_value=10000.0,
            value=0.0,                              # always starts at 0, not pre-filled
            step=1.0,
            format="%.1f",
            key=f"override_val_{selected_date}",   # resets per date
            help="Enter your corrected demand. Must be > 0 and different from AI forecast.",
        )

    with col3:
        override_reason = st.selectbox(
            "Reason for Override",
            ["", "Seasonal event", "Promotion planned", "Supply constraint",
             "Local event", "Data error correction", "Other"],
            key="override_reason",
            help="Required — select a reason for audit purposes.",
        )

    notes = st.text_area(
        "Additional Notes (optional)",
        max_chars=300,
        placeholder="E.g. Esala Perahera festival week — expect higher demand",
        key="override_notes",
    )

    # ── Validation ─────────────────────────────────────────────────────────────
    errors: list[str] = []

    if override_val <= 0:
        errors.append("❌ Override value must be greater than 0.")
    if override_val > 9999:
        errors.append("❌ Value seems unrealistically high (max 9999 units). Please verify.")
    if not override_reason:
        errors.append("❌ Please select a reason for the override.")

    is_same = override_val > 0 and round(override_val, 1) == round(current_val, 1)
    if is_same:
        errors.append("⚠️ Override value matches AI forecast exactly. Enter a different value.")

    for err in errors:
        css = "alert-warning" if err.startswith("⚠️") else "alert-info"
        st.markdown(f'<div class="{css}">{err}</div>', unsafe_allow_html=True)

    # Large deviation warning — not a blocker
    if override_val > 0 and not is_same and current_val > 0:
        deviation = abs(override_val - current_val) / current_val
        if deviation > 0.5:
            st.markdown(
                f'<div class="alert-warning">⚠️ Your override ({override_val:.0f}) differs from the '
                f'AI forecast ({current_val:.0f}) by {deviation*100:.0f}%. Double-check before saving.</div>',
                unsafe_allow_html=True,
            )

    st.markdown("")

    save_disabled = bool(errors)

    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        clicked = st.button(
            "💾 Save Override",
            disabled=save_disabled,
            type="primary",
            key="save_override_btn",
            help="Disabled until all validation errors are resolved." if save_disabled else "Save this override.",
        )

    if clicked and not save_disabled:
        ok = _apply_override(product, selected_date, override_val, override_reason, notes, current_val)
        if ok:
            st.session_state.override_saved = True
            st.session_state.override_saved_for = selected_date

    # Show success ONLY if we just saved (not on re-renders / tab switches)
    if st.session_state.override_saved and st.session_state.override_saved_for == selected_date:
        with col_status:
            st.success(
                f"✅ Override saved for {selected_date}: **{override_val:.0f} units** "
                f"(AI was {current_val:.0f}). Reason: {override_reason}"
            )
        # Reset flag immediately so success doesn't re-fire
        st.session_state.override_saved = False


# ── Override history ───────────────────────────────────────────────────────────

def _render_override_history(product: dict) -> None:
    """Show all past manual overrides for this product from the DB."""
    st.markdown('<div class="section-title">🔁 Override History</div>', unsafe_allow_html=True)

    overrides = fetch_overrides(product.get("product_code", ""))

    if not overrides:
        st.info(
            "No manual overrides recorded yet for this product. "
            "Use the Manual Override tab to create one."
        )
        return

    st.markdown(
        f'<div class="alert-info">'
        f'<strong>{len(overrides)} override(s)</strong> recorded for '
        f'<strong>{product.get("product_name","this product")}</strong>.'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    rows = []
    for ov in overrides:
        ai_val = ov.get("original_ai_demand")
        new_val = ov.get("predicted_demand", 0)
        diff = ""
        if ai_val:
            delta = new_val - ai_val
            arrow = "▲" if delta > 0 else "▼"
            diff = f"{arrow} {abs(delta):.1f} ({abs(delta/ai_val)*100:.0f}%)"

        rows.append({
            "Date": ov.get("forecast_date", "—"),
            "AI Forecast": f"{ai_val:.1f}" if ai_val else "—",
            "Override Value": f"{new_val:.1f}",
            "Change": diff,
            "Reason": ov.get("override_reason", "—"),
            "Notes": ov.get("override_notes", "—") or "—",
            "Saved At": ov.get("created_at", "")[:16].replace("T", " ") if ov.get("created_at") else "—",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    csv = pd.DataFrame(rows).to_csv(index=False)
    st.download_button(
        "📥 Download Override History (CSV)",
        data=csv,
        file_name=f"overrides_{product.get('product_code','')}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key=f"dl_overrides_{product.get('product_code','')}",
    )


# ── Apply override ─────────────────────────────────────────────────────────────

def _apply_override(
    product: dict,
    date_str: str,
    value: float,
    reason: str,
    notes: str,
    original_ai: float,
) -> bool:
    """Persist manual override to DB. Returns True on success."""
    override_row = [{
        "date": date_str,
        "predicted": round(value, 2),
        "confidence": 1.0,
    }]
    metrics = {
        "mape": 0.0, "rmse": 0.0, "mae": 0.0, "r2_score": 1.0,
    }
    ok = save_forecast(
        product.get("product_code", ""),
        override_row,
        metrics,
        model_version="manual_override",
        is_manual_override=True,
        original_ai_demand=original_ai,
        override_reason=reason,
        override_notes=notes,
    )
    if not ok:
        st.error("❌ Failed to save override. Check database connection.")
    return ok