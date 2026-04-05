"""
ui/components/forecast_tab.py
==============================
Tab 1 — Forecast View
Renders: combined historical + forecast chart, impact factor bars,
         summary metrics, model performance expander, weather badge.
"""

from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from services.weather_service import get_kandy_weather
from services.forecast_service import get_active_model_version
from data.forecast_repository import fetch_overrides


def render_forecast_tab(
    hist_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    metrics: dict,
    product: dict,
    show_confidence: bool,
    show_weather_impact: bool,
) -> None:
    """Render the full Forecast View tab."""

    model_version = get_active_model_version()
    weather = get_kandy_weather()
    overrides = fetch_overrides(product.get("product_code", ""))
    override_map = {ov["forecast_date"]: ov for ov in overrides}

    # ── Top badges row ─────────────────────────────────────────────────────────
    badge_row = f'<span class="badge badge-model">🧠 Model: {model_version}</span> '
    if weather.get("available"):
        badge_row += (
            f'<span class="badge badge-weather">🌤 {weather["condition"]} · {weather["temp_c"]}°C</span> '
        )
    if override_map:
        badge_row += f'<span class="badge badge-holiday">✏️ {len(override_map)} Override(s)</span> '
    st.markdown(badge_row, unsafe_allow_html=True)
    st.markdown("")

    if forecast_df.empty:
        st.warning("No forecast data available. Check the forecasting service.")
        return

    # ── Main chart ─────────────────────────────────────────────────────────────
    fig = _build_forecast_chart(hist_df, forecast_df, show_confidence, override_map)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    # ── Impact factor bar ──────────────────────────────────────────────────────
    fig2 = _build_impact_chart(forecast_df)
    st.plotly_chart(fig2, use_container_width=True, config={"displaylogo": False})

    # ── Summary metrics ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">📊 Forecast Summary</div>', unsafe_allow_html=True)
    _render_summary_metrics(forecast_df, metrics)

    # ── Model performance ──────────────────────────────────────────────────────
    with st.expander("📈 Model Performance Metrics", expanded=False):
        _render_model_metrics(metrics)

    # ── Next-7-day table ───────────────────────────────────────────────────────
    with st.expander("📅 Next 7-Day Forecast at a Glance", expanded=True):
        _render_weekly_preview(forecast_df)


# ── private builders ───────────────────────────────────────────────────────────

def _build_forecast_chart(
    hist_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    show_confidence: bool,
    override_map: dict | None = None,
) -> go.Figure:
    fig = go.Figure()

    # Historical (last 30 days)
    if not hist_df.empty and "transaction_date" in hist_df.columns:
        recent = hist_df.tail(30)
        fig.add_trace(
            go.Scatter(
                x=recent["transaction_date"],
                y=recent["quantity_sold"],
                mode="lines+markers",
                name="Historical Sales",
                line=dict(color="#3B82F6", width=2),
                marker=dict(size=5, color="#2563EB"),
                hovertemplate="<b>%{x|%d %b}</b><br>Actual: %{y:.0f} units<extra></extra>",
            )
        )

    # Confidence band
    if show_confidence and not forecast_df.empty:
        fig.add_trace(
            go.Scatter(
                x=pd.concat([forecast_df["date"], forecast_df["date"][::-1]]),
                y=pd.concat(
                    [
                        forecast_df["predicted"] * 1.1,
                        forecast_df["predicted"][::-1] * 0.9,
                    ]
                ),
                fill="toself",
                fillcolor="rgba(234,88,12,0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                name="Confidence ±10%",
                hoverinfo="skip",
            )
        )

    # Forecast line
    if not forecast_df.empty:
        fig.add_trace(
            go.Scatter(
                x=forecast_df["date"],
                y=forecast_df["predicted"],
                mode="lines+markers",
                name="Forecast",
                line=dict(color="#EA580C", width=3, dash="dash"),
                marker=dict(
                    size=8,
                    color=[
                        "#DC2626" if r.is_holiday else "#0891B2" if r.is_weekend else "#EA580C"
                        for _, r in forecast_df.iterrows()
                    ],
                    line=dict(color="white", width=1.5),
                ),
                hovertemplate=(
                    "<b>%{x|%d %b %Y}</b><br>"
                    "Forecast: <b>%{y:.0f} units</b><br>"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=dict(text="Demand Forecast — Historical vs Predicted", font=dict(size=15)),
        xaxis_title="Date",
        yaxis_title="Units",
        height=420,
        margin=dict(t=50, b=40, l=50, r=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(148,163,184,0.2)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.2)")

    # ── Override markers ───────────────────────────────────────────────────────
    # Show overridden values as distinct star markers on the chart
    if override_map and not forecast_df.empty:
        import pandas as _pd
        ov_dates, ov_vals, ov_orig, ov_reasons = [], [], [], []
        for _, row in forecast_df.iterrows():
            date_str = row["date"].strftime("%Y-%m-%d")
            if date_str in override_map:
                ov = override_map[date_str]
                ov_dates.append(row["date"])
                ov_vals.append(float(ov["predicted_demand"]))
                ov_orig.append(float(ov.get("original_ai_demand") or row["predicted"]))
                ov_reasons.append(ov.get("override_reason") or "Manual override")

        if ov_dates:
            # Original AI values shown as faded circles
            fig.add_trace(go.Scatter(
                x=ov_dates,
                y=ov_orig,
                mode="markers",
                name="Original AI (overridden)",
                marker=dict(
                    size=10,
                    color="rgba(234,88,12,0.3)",
                    symbol="circle",
                    line=dict(color="#EA580C", width=1.5),
                ),
                hovertemplate="<b>%{x|%d %b}</b><br>Original AI: %{y:.0f} units<extra>Overridden</extra>",
            ))
            # Override values as bold stars — one trace per override point
            # so each star renders independently with its own hover text
            for ov_d, ov_v, ov_r in zip(ov_dates, ov_vals, ov_reasons):
                fig.add_trace(
                    x=[ov_d],
                    y=[ov_v],
                    mode="markers+text",
                    name="Manual Override",
                    text=["✏️"],
                    textposition="top center",
                    showlegend=False,
                    marker=dict(
                        size=14,
                        color="#7C3AED",
                        symbol="star",
                        line=dict(color="white", width=1.5),
                    ),
                    hovertemplate=(
                        f"<b>{ov_d.strftime('%d %b')}</b><br>"
                        f"Override: <b>{ov_v:.0f} units</b><br>"
                        f"Reason: {ov_r or 'Manual override'}"
                        "<extra>Manual Override</extra>"
                    ),
                )
            # Add one invisible trace just for the legend entry
            fig.add_trace(go.Scatter(
                x=[None], y=[None],
                mode="markers",
                name="Manual Override",
                marker=dict(size=14, color="#7C3AED", symbol="star",
                            line=dict(color="white", width=1.5)),
                showlegend=True,
            ))

    return fig


def _build_impact_chart(forecast_df: pd.DataFrame) -> go.Figure:
    factors_df = forecast_df.copy()
    factors_df["factor"] = 1.0
    factors_df.loc[factors_df["is_weekend"].astype(bool), "factor"] = 1.25
    factors_df.loc[factors_df["is_holiday"].astype(bool), "factor"] = 1.5

    colors = [
        "#DC2626" if r.is_holiday else "#0891B2" if r.is_weekend else "#059669"
        for _, r in factors_df.iterrows()
    ]
    labels = [
        "🎉 Holiday" if r.is_holiday else "📅 Weekend" if r.is_weekend else "📋 Weekday"
        for _, r in factors_df.iterrows()
    ]

    fig = go.Figure(
        go.Bar(
            x=factors_df["date"],
            y=factors_df["factor"],
            marker_color=colors,
            text=labels,
            textposition="outside",
            textfont=dict(size=9),
            hovertemplate="<b>%{x|%d %b}</b><br>Factor: %{y:.2f}×<br>%{text}<extra></extra>",
            name="Day Impact Factor",
        )
    )
    fig.update_layout(
        title=dict(text="Day-Type Impact Factors (Weekend / Holiday)", font=dict(size=13)),
        xaxis_title="Date",
        yaxis_title="Demand Multiplier",
        height=260,
        margin=dict(t=45, b=30, l=50, r=30),
        yaxis=dict(range=[0, 2.1]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.2)")

    # Reference line at 1×
    fig.add_hline(y=1.0, line_dash="dot", line_color="rgba(148,163,184,0.6)", annotation_text="Baseline")
    return fig


def _render_summary_metrics(forecast_df: pd.DataFrame, metrics: dict) -> None:
    col1, col2, col3, col4 = st.columns(4)

    total    = forecast_df["predicted"].sum()
    avg      = forecast_df["predicted"].mean()
    peak_row = forecast_df.loc[forecast_df["predicted"].idxmax()]
    r2       = metrics.get("r2_score", 0)
    grade    = metrics.get("grade", "")
    g_color  = metrics.get("grade_color", "#2563EB")
    g_emoji  = metrics.get("grade_emoji", "🔵")

    with col1:
        days = len(forecast_df)
        st.metric("Total Forecast", f"{total:,.0f} units", delta=f"{days}-day window")
    with col2:
        st.metric("Daily Average", f"{avg:.1f} units")
    with col3:
        peak_date = peak_row["date"].strftime("%d %b") if hasattr(peak_row["date"], "strftime") else str(peak_row["date"])
        st.metric("Peak Day", f"{peak_row['predicted']:.0f} units", delta=peak_date)
    with col4:
        st.metric("Model Accuracy", f"{r2*100:.1f}%", delta=f"R² = {r2:.3f}")
        st.markdown(
            f'<span class="badge" style="background:{g_color}22;color:{g_color}">'
            f'{g_emoji} {grade}</span>',
            unsafe_allow_html=True,
        )


def _render_model_metrics(metrics: dict) -> None:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("MAPE", f"{metrics.get('mape', 0):.1f}%")
        st.caption("Mean Absolute % Error")
    with col2:
        st.metric("RMSE", f"{metrics.get('rmse', 0):.2f}")
        st.caption("Root Mean Squared Error")
    with col3:
        st.metric("MAE", f"{metrics.get('mae', 0):.2f}")
        st.caption("Mean Absolute Error")
    with col4:
        r2 = metrics.get("r2_score", 0)
        st.metric("R² Score", f"{r2:.4f}")
        st.caption("Goodness of Fit")

    st.markdown(
        '<div class="alert-info" style="margin-top:.75rem">'
        '⚠️ <strong>Note:</strong> Model trained on Sunrise Supermarket client sales data (2024–2026). '
        'R² and other metrics reflect performance on the held-out test set.'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_weekly_preview(forecast_df: pd.DataFrame) -> None:
    preview = forecast_df.head(7).copy()
    preview["Day"] = preview["date"].dt.strftime("%a, %d %b")
    preview["Type"] = preview.apply(
        lambda r: "🎉 Holiday" if r.is_holiday else "📅 Weekend" if r.is_weekend else "📋 Weekday",
        axis=1,
    )
    preview["Predicted Demand"] = preview["predicted"].map(lambda v: f"{v:.0f} units")
    preview["Confidence"] = preview["confidence"].map(lambda v: f"{v*100:.0f}%")

    st.dataframe(
        preview[["Day", "Type", "Predicted Demand", "Confidence"]],
        use_container_width=True,
        hide_index=True,
    )