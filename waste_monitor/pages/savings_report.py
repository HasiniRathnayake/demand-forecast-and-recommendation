"""
pages/savings_report.py
Author : IT24103258
"""

from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from utils.database import fetch_ai_performance, fetch_waste_records
from utils.helpers  import format_lkr


def show_savings_report() -> None:
    st.markdown("<h1 style='font-size:3.5rem;font-weight:900;letter-spacing:-1px;'>AI Savings Analysis</h1>", unsafe_allow_html=True)
    st.divider()

    ai_df    = fetch_ai_performance()
    waste_df = fetch_waste_records()

    if ai_df.empty or waste_df.empty:
        st.warning("Insufficient data to generate the savings report.")
        return

    evaluated = (
        ai_df[ai_df["actual_sales"].notna()].copy()
        if "actual_sales" in ai_df.columns else pd.DataFrame()
    )
    if evaluated.empty:
        st.warning("No evaluated predictions available. Add actual sales comparisons in the AI Performance page first.")
        return

    total_waste_loss  = float(waste_df["estimated_loss"].sum())
    avg_error         = float(evaluated["error_percentage"].mean())
    accuracy          = 100.0 - avg_error

    waste_wo_ai       = total_waste_loss * 1.4
    overstock_wo      = waste_wo_ai * 0.3
    lost_rev_wo       = waste_wo_ai * 0.5
    total_before      = waste_wo_ai + overstock_wo + lost_rev_wo

    current_overstock = total_waste_loss * 0.2
    current_lost_rev  = total_waste_loss * 0.3
    total_after       = total_waste_loss + current_overstock + current_lost_rev

    savings_pct       = (total_before - total_after) / total_before * 100
    total_savings     = total_before - total_after

    st.subheader("Before vs After AI Implementation")
    b1, b2 = st.columns(2)

    with b1:
        st.markdown("**Before AI (Estimated)**")
        st.dataframe(pd.DataFrame({
            "Metric": ["Total Waste Loss", "Overstock Costs", "Lost Revenue", "Total Impact"],
            "Amount": [format_lkr(waste_wo_ai), format_lkr(overstock_wo),
                       format_lkr(lost_rev_wo), format_lkr(total_before)],
        }), use_container_width=True, hide_index=True)

    with b2:
        st.markdown("**After AI (Actual)**")
        st.dataframe(pd.DataFrame({
            "Metric":    ["Total Waste Loss", "Overstock Costs", "Lost Revenue", "Total Impact"],
            "Amount":    [format_lkr(total_waste_loss), format_lkr(current_overstock),
                          format_lkr(current_lost_rev), format_lkr(total_after)],
            "Reduction": [
                f"-{(waste_wo_ai - total_waste_loss) / waste_wo_ai * 100:.1f}%",
                f"-{(overstock_wo - current_overstock) / overstock_wo * 100:.1f}%",
                f"-{(lost_rev_wo  - current_lost_rev)  / lost_rev_wo  * 100:.1f}%",
                f"-{savings_pct:.1f}%",
            ],
        }), use_container_width=True, hide_index=True)

    st.divider()

    s1, s2, s3 = st.columns(3)
    with s1: st.metric("Total AI Savings",         format_lkr(total_savings), delta=f"{savings_pct:.1f}% cost reduction")
    with s2: st.metric("AI Forecast Accuracy",     f"{accuracy:.1f}%")
    with s3: st.metric("Projected Annual Savings", format_lkr(total_savings))

    st.divider()
    st.subheader("Savings Breakdown")
    sc1, sc2 = st.columns(2)

    with sc1:
        st.markdown("**Monthly Savings Trend**")
        mw = waste_df.copy()
        mw["month"] = mw["waste_date"].dt.to_period("M")
        monthly = mw.groupby("month")["estimated_loss"].sum().reset_index()
        monthly["month"]                = monthly["month"].astype(str)
        monthly["estimated_without_ai"] = monthly["estimated_loss"] * 1.4
        monthly["savings"]              = monthly["estimated_without_ai"] - monthly["estimated_loss"]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=monthly["month"], y=monthly["estimated_loss"],
                             name="Actual (with AI)", marker_color="#2563eb"))
        fig.add_trace(go.Bar(x=monthly["month"], y=monthly["savings"],
                             name="AI Savings", marker_color="#16a34a"))
        fig.update_layout(barmode="stack", height=380,
                          xaxis_title="Month", yaxis_title="Amount (Rs.)",
                          margin=dict(t=10, b=40, l=40, r=10))
        st.plotly_chart(fig, use_container_width=True)

    with sc2:
        st.markdown("**Savings Contribution by Product**")
        prod_sav = evaluated.groupby("product_code").agg(
            error_pct=("error_percentage", "mean"),
            count    =("predicted_demand",  "count"),
        ).reset_index()
        prod_sav["contribution"] = (100 - prod_sav["error_pct"]) * prod_sav["count"]
        prod_sav = prod_sav.nlargest(8, "contribution")
        fig = px.pie(prod_sav, values="contribution", names="product_code",
                     hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=380, showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Executive Summary")

    if accuracy > 90:
        insight = "The AI system is performing exceptionally well. Consider expanding forecasting to more product categories."
    elif accuracy > 80:
        insight = "Good performance with room for improvement. Focus on reducing error in the highest-error products."
    else:
        insight = "Moderate performance. Review data quality and model assumptions to improve forecast accuracy."

    ec1, ec2 = st.columns([2, 1])
    with ec1:
        st.info(
            f"**AI Investment Performance**\n\n"
            f"The AI system has generated **{format_lkr(total_savings)}** in total savings "
            f"with an average forecast accuracy of **{accuracy:.1f}%**.\n\n"
            f"This represents a **{savings_pct:.1f}%** reduction in waste-related costs "
            f"compared to pre-AI estimates.\n\n"
            f"**Key Insight:** {insight}"
        )
    with ec2:
        st.dataframe(pd.DataFrame({
            "Metric": ["Total Savings", "AI Accuracy", "Cost Reduction",
                       "Products with AI", "Total Predictions"],
            "Value":  [format_lkr(total_savings), f"{accuracy:.1f}%", f"{savings_pct:.1f}%",
                       str(evaluated["product_code"].nunique()), str(len(evaluated))],
        }), use_container_width=True, hide_index=True)