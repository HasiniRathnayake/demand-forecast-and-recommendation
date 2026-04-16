"""
pages/ai_performance.py
Author : IT24103258
"""

from __future__ import annotations
from datetime import date, datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from utils.database   import fetch_ai_performance, fetch_demand_forecasts, upsert_ai_comparison
from utils.helpers    import calculate_accuracy_metrics, fmt_date, fmt_datetime, fmt_pct, fmt_signed
from utils.validators import validate_actual_sales


def show_ai_performance_comparison(start: date, end: date) -> None:
    st.markdown("""
<style>
div[data-testid="stForm"] div.stButton > button {
    background-color: #dc2626 !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: 600;
}
div[data-testid="stForm"] div.stButton > button:hover {
    background-color: #b91c1c !important;
}
</style>
""", unsafe_allow_html=True)

    all_forecasts = fetch_demand_forecasts()
    ai_df         = fetch_ai_performance(start, end)

    # ── Add Comparison Form ───────────────────────────────────────────────────
    st.markdown("<h1 style='font-size:3.5rem;font-weight:900;letter-spacing:-1px;'> Actual vs Predicted Comparison</h1>", unsafe_allow_html=True)

    if all_forecasts.empty:
        st.warning("No demand forecasts found. Please generate forecasts in the Demand Forecast module first.")
    else:
        st.success(f"{len(all_forecasts):,} forecasts available for comparison.")

        with st.form("comparison_form"):
            col1, col2 = st.columns(2)

            with col1:
                options = all_forecasts.apply(
                    lambda r: f"{r['product_code']}  |  {r['forecast_date'].strftime('%Y-%m-%d')}  |  Predicted: {r['predicted_demand']:.2f}",
                    axis=1,
                ).tolist()
                idx       = st.selectbox("Select Forecast *", range(len(options)),
                                         format_func=lambda i: options[i])
                row       = all_forecasts.iloc[idx]
                predicted = float(row["predicted_demand"])
                st.info(
                    f"**Product:** {row['product_code']}  \n"
                    f"**Date:** {row['forecast_date'].strftime('%Y-%m-%d')}  \n"
                    f"**Predicted:** {predicted:.2f}"
                )

            with col2:
                actual = st.number_input(
                    "Actual Sales *", min_value=0.0,
                    value=predicted, step=0.1, format="%.2f",
                    help="Enter the real sales quantity recorded for this date.",
                )
                diff     = actual - predicted
                diff_pct = (diff / predicted * 100) if predicted > 0 else 0.0
                if diff >= 0:
                    st.info(f"Difference: +{diff:.2f} (+{diff_pct:.2f}%)")
                else:
                    st.warning(f"Difference: {diff:.2f} ({diff_pct:.2f}%)")

            submitted = st.form_submit_button("Save Comparison", use_container_width=True)

        if submitted:
            if row["forecast_date"].date() > date.today():
                st.error("Cannot add actual sales for a future prediction date. Please select a forecast with a past or today's date.")
            else:
                ok_val, msg_val = validate_actual_sales(actual)
                if not ok_val:
                    st.error(msg_val)
                else:
                    with st.spinner("Saving..."):
                        ok, msg = upsert_ai_comparison(
                            str(row["forecast_id"]), str(row["product_code"]),
                            row["forecast_date"].date(), predicted, actual,
                        )
                    if ok:
                        st.success(f"Comparison for **{row['product_code']}** on {row['forecast_date'].strftime('%Y-%m-%d')} saved successfully.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(msg)

    # ── Prediction Records Table ──────────────────────────────────────────────
    st.divider()
    st.subheader("Prediction Records")

    if ai_df.empty:
        st.info("No prediction records for the selected period.")
    else:
        f1, f2 = st.columns(2)
        with f1:
            products    = ["All"] + sorted(ai_df["product_code"].unique().tolist())
            sel_product = st.selectbox("Filter by Product", products, key="wpm_prod_filter")
        with f2:
            sel_status  = st.selectbox("Status", ["All", "Evaluated", "Pending"], key="wpm_status_filter")

        filtered = ai_df.copy()
        if sel_product != "All":
            filtered = filtered[filtered["product_code"] == sel_product]
        if sel_status == "Evaluated":
            filtered = filtered[filtered["actual_sales"].notna()]
        elif sel_status == "Pending":
            filtered = filtered[filtered["actual_sales"].isna()]

        k1, k2, k3, k4 = st.columns(4)
        evaluated_n = int(filtered["actual_sales"].notna().sum())
        pending_n   = int(filtered["actual_sales"].isna().sum())
        with k1: st.metric("Total Records", len(filtered))
        with k2: st.metric("Evaluated",     evaluated_n)
        with k3: st.metric("Pending",       pending_n)
        with k4:
            if evaluated_n > 0 and "error_percentage" in filtered.columns:
                avg_e = filtered[filtered["actual_sales"].notna()]["error_percentage"].mean()
                st.metric("Avg Error", f"{avg_e:.2f}%")

        disp_cols = ["forecast_date", "product_code", "predicted_demand",
                     "actual_sales", "error_value", "error_percentage", "evaluated_at"]
        disp = filtered[[c for c in disp_cols if c in filtered.columns]].copy()

        if "forecast_date"    in disp.columns: disp["forecast_date"]    = disp["forecast_date"].apply(fmt_date)
        if "predicted_demand" in disp.columns: disp["predicted_demand"] = disp["predicted_demand"].apply(lambda x: f"{x:.2f}")
        if "actual_sales"     in disp.columns: disp["actual_sales"]     = disp["actual_sales"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "Pending")
        if "error_value"      in disp.columns: disp["error_value"]      = disp["error_value"].apply(fmt_signed)
        if "error_percentage" in disp.columns: disp["error_percentage"] = disp["error_percentage"].apply(fmt_pct)
        if "evaluated_at"     in disp.columns: disp["evaluated_at"]     = disp["evaluated_at"].apply(fmt_datetime)

        disp.columns = ["Date", "Product", "Predicted", "Actual", "Error Value", "Error %", "Evaluated At"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

        csv = filtered.to_csv(index=False)
        st.download_button(
            label="Export to CSV",
            data=csv,
            file_name=f"ai_performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="export_ai_perf",
        )


def show_ai_performance_analytics(start: date, end: date) -> None:
    ai_df = fetch_ai_performance(start, end)

    st.markdown("<h1 style='font-size:3.5rem;font-weight:900;letter-spacing:-1px;'>AI Performance Analytics</h1>", unsafe_allow_html=True)
    st.divider()

    if ai_df.empty:
        st.info("No data available for the selected period.")
        return

    evaluated = ai_df[ai_df["actual_sales"].notna()].copy() if "actual_sales" in ai_df.columns else pd.DataFrame()
    if evaluated.empty:
        st.info("No evaluated records yet. Add actual sales via the Comparisons & Records tab.")
        return

    m = calculate_accuracy_metrics(evaluated)
    if m:
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: st.metric("Evaluated", m["count"])
        with m2: st.metric("MAE",       f"{m['mae']:.2f}")
        with m3: st.metric("RMSE",      f"{m['rmse']:.2f}")
        with m4: st.metric("MAPE",      f"{m['mape']:.2f}%")
        with m5: st.metric("Accuracy",  f"{100 - m['mape']:.2f}%")

    st.divider()
    st.subheader("Predicted vs Actual Sales")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=evaluated["forecast_date"], y=evaluated["predicted_demand"],
                             mode="lines+markers", name="Predicted", line=dict(color="#2563eb")))
    fig.add_trace(go.Scatter(x=evaluated["forecast_date"], y=evaluated["actual_sales"],
                             mode="lines+markers", name="Actual", line=dict(color="#16a34a")))
    fig.update_layout(height=420, xaxis_title="Date", yaxis_title="Quantity",
                      hovermode="x unified", margin=dict(t=20, b=40, l=40, r=20))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Product Performance Analysis")
    prod_err = (
        evaluated.groupby("product_code").agg(
            Avg_Error_Pct=("error_percentage", "mean"),
            Records      =("performance_id",   "count"),
        ).round(2).reset_index().sort_values("Avg_Error_Pct")
    )
    p1, p2 = st.columns(2)
    with p1:
        best = prod_err.head(10)
        fig = px.bar(best, x="product_code", y="Avg_Error_Pct",
                     title="Top 10 Best Performing Products",
                     color="Avg_Error_Pct", color_continuous_scale=["#7af2a6", "#16a34a", "#14532d"],
                     range_color=[0, best["Avg_Error_Pct"].max()])
        fig.update_layout(margin=dict(t=40, b=40, l=30, r=10))
        st.plotly_chart(fig, use_container_width=True)
    with p2:
        worst = prod_err.nlargest(10, "Avg_Error_Pct")
        fig = px.bar(worst, x="product_code", y="Avg_Error_Pct",
                     title="Top 10 Products Needing Improvement",
                     color="Avg_Error_Pct", color_continuous_scale="Reds",
                     range_color=[0, worst["Avg_Error_Pct"].max()])
        fig.update_layout(margin=dict(t=40, b=40, l=30, r=10))
        st.plotly_chart(fig, use_container_width=True)


# Backward compatibility
def show_ai_performance(start: date, end: date) -> None:
    show_ai_performance_comparison(start, end)

# ══════════════════════════════════════════════════════════════════════════════
# RL PERFORMANCE SECTION  —  Author: IT24103258
# Added below existing code — does not modify any existing functions above
# ══════════════════════════════════════════════════════════════════════════════

import os

_RL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "rl_data")


@st.cache_data
def _load_reward_dataset() -> pd.DataFrame:
    path = os.path.join(_RL_DATA_DIR, "xgb_reward_dataset.csv")
    df   = pd.read_csv(path)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["year_month"]       = df["transaction_date"].dt.to_period("M").astype(str)
    return df


@st.cache_data
def _load_model_comparison() -> pd.DataFrame:
    path = os.path.join(_RL_DATA_DIR, "model_comparison.csv")
    return pd.read_csv(path)


def show_rl_model_comparison() -> None:
    """
    RL Model Improvement — before/after comparison + graphs from CSV.
    """
    st.markdown(
        "<h1 style='font-size:3.5rem;font-weight:900;letter-spacing:-1px;'>"
        "RL Model Improvement</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Based on reinforcement learning evaluation on 27 months of historical data.")
    st.divider()

    comparison = pd.DataFrame([
        {"Model": "Random Forest (original)", "MAPE %": 3.04, "Perfect Pred %": 83.6, "Avg Reward": 5.42, "MAE": 1.863, "R²": 0.9914},
        {"Model": "Random Forest (RL v2)",    "MAPE %": 1.82, "Perfect Pred %": 91.7, "Avg Reward": 7.67, "MAE": 1.060, "R²": 0.9958},
        {"Model": "XGBoost (original)",       "MAPE %": 1.88, "Perfect Pred %": 94.9, "Avg Reward": 8.76, "MAE": 1.136, "R²": 0.9977},
        {"Model": "XGBoost RL v2  🏆",        "MAPE %": 1.23, "Perfect Pred %": 98.5, "Avg Reward": 9.66, "MAE": 0.717, "R²": 0.9989},
    ])

    # ── Key metrics ────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Best Model",          "XGBoost RL v2",  delta="RL retrained")
    with k2: st.metric("Perfect Predictions", "98.5%",          delta="+3.6% vs original")
    with k3: st.metric("MAPE Error",          "1.23%",          delta="-0.65% vs original")
    with k4: st.metric("Avg Reward Score",    "9.66 / 10",      delta="+0.90 vs original")

    st.divider()

    # ── Perfect Prediction Rate & MAPE comparison ──────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Perfect Prediction Rate")
        fig = px.bar(
            comparison, x="Model", y="Perfect Pred %",
            color="Perfect Pred %",
            color_continuous_scale=["#fca5a5", "#16a34a"],
            range_color=[80, 100],
            text="Perfect Pred %",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(height=380, margin=dict(t=20, b=60, l=30, r=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("MAPE % (Lower is Better)")
        fig = px.bar(
            comparison, x="Model", y="MAPE %",
            color="MAPE %",
            color_continuous_scale=["#16a34a", "#fca5a5"],
            range_color=[1, 4],
            text="MAPE %",
        )
        fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig.update_layout(height=380, margin=dict(t=20, b=60, l=30, r=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── MAE & Avg Reward ───────────────────────────────────────────────────
    c3, c4 = st.columns(2)
    with c3:
        st.subheader("MAE (Lower is Better)")
        fig = px.bar(
            comparison, x="Model", y="MAE",
            color="MAE",
            color_continuous_scale=["#16a34a", "#fca5a5"],
            range_color=[0.5, 2],
            text="MAE",
        )
        fig.update_traces(texttemplate="%{text:.3f}", textposition="outside")
        fig.update_layout(height=380, margin=dict(t=20, b=60, l=30, r=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with c4:
        st.subheader("Average Reward Score")
        fig = px.bar(
            comparison, x="Model", y="Avg Reward",
            color="Avg Reward",
            color_continuous_scale=["#fca5a5", "#16a34a"],
            range_color=[4, 10],
            text="Avg Reward",
        )
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig.update_layout(height=380, margin=dict(t=20, b=60, l=30, r=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Comparison table ───────────────────────────────────────────────────
    st.subheader("Full Model Comparison Table")
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    # ── Reward function explanation ────────────────────────────────────────
    st.divider()
    st.subheader("How the Reward Function Works")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.success("**✅ Perfect Prediction**  \nWithin 5% error  \nReward: **+10 points**")
    with col2:
        st.warning("**⚠️ Over-Predicted (Waste)**  \nExcess stock ordered  \nPenalty: **−2 pts per unit**")
    with col3:
        st.error("**❌ Under-Predicted (Stockout)**  \nMissed sales  \nPenalty: **−5 pts per unit**")


def show_rl_predictions() -> None:
    """
    RL Predictions — graphs loaded from xgb_reward_dataset.csv.
    """
    st.markdown(
        "<h1 style='font-size:3.5rem;font-weight:900;letter-spacing:-1px;'>"
        "RL Predictions</h1>",
        unsafe_allow_html=True,
    )
    st.caption("XGBoost RL v2 predictions vs actual sales — 27 months of historical data.")
    st.divider()

    try:
        df = _load_reward_dataset()
    except FileNotFoundError:
        st.error("CSV file not found. Make sure xgb_reward_dataset.csv is in ml/rl_data/.")
        return

    # ── Filters ────────────────────────────────────────────────────────────
    f1, f2 = st.columns(2)
    with f1:
        products    = ["All"] + sorted(df["product_code"].unique().tolist())
        sel_product = st.selectbox("Filter by Product", products, key="rl_prod_filter")
    with f2:
        months      = ["All"] + sorted(df["year_month"].unique().tolist())
        sel_month   = st.selectbox("Filter by Month", months, key="rl_month_filter")

    filtered = df.copy()
    if sel_product != "All":
        filtered = filtered[filtered["product_code"] == sel_product]
    if sel_month != "All":
        filtered = filtered[filtered["year_month"] == sel_month]

    # ── Summary metrics ────────────────────────────────────────────────────
    perfect_pct = float((filtered["reward"] == 10.0).mean() * 100)
    avg_reward  = float(filtered["reward"].mean())
    mae         = float((filtered["predicted_quantity"] - filtered["quantity_sold"]).abs().mean())

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Total Predictions", f"{len(filtered):,}")
    with k2: st.metric("Perfect Pred %",    f"{perfect_pct:.1f}%")
    with k3: st.metric("Avg Reward",        f"{avg_reward:.2f} / 10")
    with k4: st.metric("MAE",               f"{mae:.3f}")

    st.divider()

    # ── Predicted vs Actual — monthly aggregated line chart ───────────────
    st.subheader("Predicted vs Actual Sales (Monthly Average)")
    monthly = (
        filtered.groupby("year_month")
        .agg(
            Predicted=("predicted_quantity", "mean"),
            Actual   =("quantity_sold",      "mean"),
        )
        .reset_index()
        .sort_values("year_month")
    )
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["year_month"], y=monthly["Predicted"],
        mode="lines+markers", name="RL Predicted",
        line=dict(color="#2563eb", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=monthly["year_month"], y=monthly["Actual"],
        mode="lines+markers", name="Actual Sales",
        line=dict(color="#16a34a", width=2),
    ))
    fig.update_layout(
        height=420, xaxis_title="Month", yaxis_title="Avg Quantity",
        hovermode="x unified", margin=dict(t=20, b=40, l=40, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Product-level accuracy ─────────────────────────────────────────────
    st.subheader("Product-Level Accuracy")
    prod = (
        filtered.groupby("product_code")
        .agg(
            Perfect_Pct =("reward",             lambda x: (x == 10.0).mean() * 100),
            Avg_Reward  =("reward",             "mean"),
            Records     =("predicted_quantity", "count"),
        )
        .round(2).reset_index()
    )

    p1, p2 = st.columns(2)
    with p1:
        best = prod.nlargest(10, "Perfect_Pct")
        fig  = px.bar(
            best, x="product_code", y="Perfect_Pct",
            title="Top 10 Best Products (Perfect Pred %)",
            color="Perfect_Pct",
            color_continuous_scale=["#7af2a6", "#16a34a", "#14532d"],
        )
        fig.update_layout(height=380, margin=dict(t=40, b=60, l=30, r=10))
        st.plotly_chart(fig, use_container_width=True)

    with p2:
        worst = prod.nsmallest(10, "Perfect_Pct")
        fig   = px.bar(
            worst, x="product_code", y="Perfect_Pct",
            title="Top 10 Products Needing Improvement",
            color="Perfect_Pct",
            color_continuous_scale=["#dc2626", "#fca5a5"],
        )
        fig.update_layout(height=380, margin=dict(t=40, b=60, l=30, r=10))
        st.plotly_chart(fig, use_container_width=True)