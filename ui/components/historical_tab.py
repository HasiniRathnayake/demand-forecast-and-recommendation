"""
Renders: sales trend, distribution histogram, day-of-week averages,
         monthly heatmap, and summary statistics.
"""

from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def render_historical_tab(hist_df: pd.DataFrame, product: dict) -> None:
    """Render the Historical Analysis tab."""

    if hist_df.empty:
        st.warning(
            f"No historical sales data found for **{product.get('product_name', 'this product')}**.\n\n"
            "Please ensure the `daily_sales_history` table has records for this product code."
        )
        _render_empty_state_tip(product)
        return

    if "quantity_sold" not in hist_df.columns:
        st.error("Unexpected data format: 'quantity_sold' column is missing.")
        return

    # ── Row 1: Trend + Distribution ────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])

    with col1:
        fig_trend = _build_trend_chart(hist_df)
        st.plotly_chart(fig_trend, use_container_width=True, config={"displaylogo": False})

    with col2:
        fig_hist = _build_distribution_chart(hist_df)
        st.plotly_chart(fig_hist, use_container_width=True, config={"displaylogo": False})

    # ── Row 2: Day-of-week + Monthly trend ────────────────────────────────────
    col3, col4 = st.columns(2)

    with col3:
        fig_dow = _build_day_of_week_chart(hist_df)
        st.plotly_chart(fig_dow, use_container_width=True, config={"displaylogo": False})

    with col4:
        fig_monthly = _build_monthly_chart(hist_df)
        st.plotly_chart(fig_monthly, use_container_width=True, config={"displaylogo": False})

    # ── Summary statistics ─────────────────────────────────────────────────────
    st.markdown('<div class="section-title">📈 Historical Statistics</div>', unsafe_allow_html=True)
    _render_stats(hist_df)


# ── private builders ───────────────────────────────────────────────────────────

def _build_trend_chart(hist_df: pd.DataFrame) -> go.Figure:
    days = len(hist_df)
    fig = px.line(
        hist_df,
        x="transaction_date",
        y="quantity_sold",
        title=f"Sales Trend (Last {days} Days)",
        labels={"quantity_sold": "Units Sold", "transaction_date": "Date"},
    )
    fig.update_traces(line_color="#3B82F6", line_width=2)

    # Add 7-day rolling average
    hist_df = hist_df.copy()
    hist_df["rolling_7d"] = hist_df["quantity_sold"].rolling(7, min_periods=1).mean()
    fig.add_scatter(
        x=hist_df["transaction_date"],
        y=hist_df["rolling_7d"],
        mode="lines",
        name="7-Day Avg",
        line=dict(color="#EA580C", width=2, dash="dot"),
    )

    fig.update_layout(
        height=320,
        margin=dict(t=45, b=30, l=50, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(148,163,184,0.2)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.2)")
    return fig


def _build_distribution_chart(hist_df: pd.DataFrame) -> go.Figure:
    fig = px.histogram(
        hist_df,
        x="quantity_sold",
        nbins=20,
        title="Sales Distribution",
        labels={"quantity_sold": "Units Sold"},
        color_discrete_sequence=["#7C3AED"],
    )
    fig.update_traces(marker_line_color="white", marker_line_width=1)
    fig.update_layout(
        height=320,
        margin=dict(t=45, b=30, l=50, r=20),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.2)")
    return fig


def _build_day_of_week_chart(hist_df: pd.DataFrame) -> go.Figure:
    df = hist_df.copy()
    df["day_of_week"] = df["transaction_date"].dt.day_name()

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekly = (
        df.groupby("day_of_week")["quantity_sold"]
        .agg(["mean", "std"])
        .reindex(order)
        .fillna(0)
    )

    colors = ["#0891B2" if d in ("Saturday", "Sunday") else "#3B82F6" for d in order]

    fig = go.Figure(
        go.Bar(
            x=weekly.index,
            y=weekly["mean"],
            error_y=dict(type="data", array=weekly["std"].values, visible=True),
            marker_color=colors,
            marker_line_color="white",
            marker_line_width=1,
            hovertemplate="<b>%{x}</b><br>Avg: %{y:.1f} units<extra></extra>",
        )
    )
    fig.update_layout(
        title="Avg Sales by Day of Week",
        xaxis_title="Day",
        yaxis_title="Avg Units Sold",
        height=310,
        margin=dict(t=45, b=30, l=50, r=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(tickangle=-30)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.2)")
    return fig


def _build_monthly_chart(hist_df: pd.DataFrame) -> go.Figure:
    df = hist_df.copy()
    df["month_label"] = df["transaction_date"].dt.strftime("%b %Y")
    df["month_order"] = df["transaction_date"].dt.to_period("M")
    monthly = (
        df.groupby(["month_order", "month_label"])["quantity_sold"]
        .sum()
        .reset_index()
        .sort_values("month_order")
    )

    fig = go.Figure(
        go.Bar(
            x=monthly["month_label"],
            y=monthly["quantity_sold"],
            marker_color="#059669",
            marker_line_color="white",
            marker_line_width=1,
            hovertemplate="<b>%{x}</b><br>Total: %{y:.0f} units<extra></extra>",
        )
    )
    fig.update_layout(
        title="Monthly Total Sales",
        xaxis_title="Month",
        yaxis_title="Total Units Sold",
        height=310,
        margin=dict(t=45, b=30, l=50, r=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(tickangle=-30)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.2)")
    return fig


def _render_stats(hist_df: pd.DataFrame) -> None:
    sales = hist_df["quantity_sold"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Mean / Day", f"{sales.mean():.1f}")
    c2.metric("Peak Day",   f"{sales.max():.0f}")
    c3.metric("Min Day",    f"{sales.min():.0f}")
    c4.metric("Std Dev",    f"{sales.std():.1f}")
    c5.metric("Total",      f"{sales.sum():,.0f}")

    # Promotion lift (if column exists)
    if "is_promotion" in hist_df.columns:
        promo = hist_df[hist_df["is_promotion"] == True]["quantity_sold"]
        no_promo = hist_df[hist_df["is_promotion"] == False]["quantity_sold"]
        if not promo.empty and not no_promo.empty:
            lift = ((promo.mean() - no_promo.mean()) / no_promo.mean()) * 100
            st.markdown(
                f'<div class="alert-success" style="margin-top:.6rem">'
                f'📣 <strong>Promotion Lift:</strong> Sales are ~{lift:.1f}% higher on promotion days '
                f'({promo.mean():.1f} vs {no_promo.mean():.1f} avg units)'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_empty_state_tip(product: dict) -> None:
    code = product.get("product_code", "UNKNOWN")
    st.markdown(
        f"""
        <div class="alert-info">
        💡 <strong>To populate mock sales data:</strong><br>
        Run the SQL insert script in <code>sql/insert_mock_data.sql</code>
        for product code <code>{code}</code>.
        </div>
        """,
        unsafe_allow_html=True,
    )