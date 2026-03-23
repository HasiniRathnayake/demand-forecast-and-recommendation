"""
pages/dashboard.py
Author : IT24103258
"""

from __future__ import annotations
from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st
from waste_monitor.utils.database import fetch_ai_performance, fetch_waste_records
from waste_monitor.utils.helpers  import fmt_date, fmt_pct, format_lkr


def show_dashboard(start: date, end: date) -> None:

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    waste_df = fetch_waste_records(start, end)
    ai_df    = fetch_ai_performance(start, end)

    k1, k2, k3, k4, k5 = st.columns(5)

    total_waste = float(waste_df["quantity_wasted"].sum()) if not waste_df.empty else 0.0
    total_loss  = float(waste_df["estimated_loss"].sum())  if not waste_df.empty else 0.0

    valid_errors = (
        ai_df["error_percentage"].dropna()
        if not ai_df.empty and "error_percentage" in ai_df.columns
        else pd.Series(dtype=float)
    )
    avg_err  = float(valid_errors.mean()) if not valid_errors.empty else None
    accuracy = (100 - avg_err) if avg_err is not None else None
    ai_savings = (
        total_loss * (accuracy / 100) * 0.5 if accuracy is not None else total_loss * 0.15
    )

    with k1: st.metric("Total Waste",       f"{total_waste:,.2f} kg")
    with k2: st.metric("Financial Loss",     format_lkr(total_loss))
    with k3: st.metric("Est. AI Savings",    format_lkr(ai_savings))
    with k4: st.metric("Avg Forecast Error", f"{avg_err:.2f}%" if avg_err is not None else "N/A")
    with k5: st.metric("AI Accuracy",        f"{accuracy:.2f}%" if accuracy is not None else "N/A")

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Waste by Reason")
        if not waste_df.empty:
            grp = waste_df.groupby("waste_reason")["quantity_wasted"].sum().reset_index()
            fig = px.pie(grp, values="quantity_wasted", names="waste_reason",
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No waste data for the selected period.")

    with c2:
        st.subheader("AI Forecast Error Trend")
        if not ai_df.empty and "error_percentage" in ai_df.columns:
            valid = ai_df[ai_df["error_percentage"].notna()]
            if not valid.empty:
                daily = valid.groupby("forecast_date")["error_percentage"].mean().reset_index()
                fig   = px.line(daily, x="forecast_date", y="error_percentage",
                                markers=True, color_discrete_sequence=["#2563eb"])
                fig.update_layout(xaxis_title="Date", yaxis_title="Error (%)",
                                  margin=dict(t=10, b=30, l=30, r=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No evaluated predictions yet.")
        else:
            st.info("No AI performance data available.")

    st.subheader("AI Error Analysis by Product")
    if not ai_df.empty and "actual_sales" in ai_df.columns:
        evaluated = ai_df[ai_df["actual_sales"].notna()]
        if not evaluated.empty:
            tbl = evaluated.groupby("product_code").agg(
                Avg_Predicted  =("predicted_demand", "mean"),
                Avg_Actual     =("actual_sales",     "mean"),
                Avg_Error_Value=("error_value",      "mean"),
                Avg_Error_Pct  =("error_percentage", "mean"),
                Records        =("performance_id",   "count"),
            ).round(2).reset_index()
            tbl.columns = ["Product", "Avg Predicted", "Avg Actual",
                           "Avg Error Value", "Avg Error %", "Records"]
            st.dataframe(tbl, use_container_width=True, hide_index=True)
        else:
            st.info("No evaluated predictions available.")
    else:
        st.info("No AI performance data available.")

    st.subheader("Recent Activity")
    r1, r2 = st.columns(2)

    with r1:
        st.markdown("**Recent Waste Records**")
        if not waste_df.empty:
            rw = waste_df.head(5)[
                ["waste_date", "product_code", "quantity_wasted", "waste_reason", "estimated_loss"]
            ].copy()
            rw["waste_date"]     = rw["waste_date"].apply(fmt_date)
            rw["estimated_loss"] = rw["estimated_loss"].apply(format_lkr)
            rw.columns = ["Date", "Product", "Qty (kg)", "Reason", "Est. Loss"]
            st.dataframe(rw, use_container_width=True, hide_index=True)
        else:
            st.info("No recent waste records.")

    with r2:
        st.markdown("**Recent AI Predictions**")
        if not ai_df.empty:
            ra = ai_df.head(5)[
                ["forecast_date", "product_code", "predicted_demand", "actual_sales", "error_percentage"]
            ].copy()
            ra["forecast_date"]    = ra["forecast_date"].apply(fmt_date)
            ra["predicted_demand"] = ra["predicted_demand"].apply(lambda x: f"{x:.2f}")
            ra["actual_sales"]     = ra["actual_sales"].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else "Pending"
            )
            ra["error_percentage"] = ra["error_percentage"].apply(fmt_pct)
            ra.columns = ["Date", "Product", "Predicted", "Actual", "Error %"]
            st.dataframe(ra, use_container_width=True, hide_index=True)
        else:
            st.info("No recent AI predictions.")