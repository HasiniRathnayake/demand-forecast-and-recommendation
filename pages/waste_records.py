"""
pages/waste_records.py
Author : IT24103258
"""

from __future__ import annotations
from datetime import date, datetime
import time
import plotly.express as px
import streamlit as st
from utils.database   import fetch_waste_records, insert_waste_record, product_code_exists
from utils.helpers    import format_lkr, fmt_date, fmt_datetime
from utils.validators import (
    VALID_WASTE_REASONS, MAX_PRICE_PER_KG, MAX_QUANTITY_KG,
    validate_waste_record_form,
)


def show_waste_records(start: date, end: date) -> None:
    st.markdown("<h1 style='font-size:3.5rem;font-weight:900;letter-spacing:-1px;'>Waste Records Management</h1>", unsafe_allow_html=True)
    st.divider()

    st.markdown("""
<style>
div[data-testid="stExpander"] summary span {
    color: #2563eb;
    font-weight: 700;
}
div[data-testid="stForm"] div.stButton > button {
    background-color: #16a34a !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: 600;
}
div[data-testid="stForm"] div.stButton > button:hover {
    background-color: #15803d !important;
}
</style>
""", unsafe_allow_html=True)

    with st.expander("Add New Waste Record", expanded=True):
        with st.form("waste_record_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                product_code = st.text_input(
                    "Product Code *",
                    placeholder="e.g. RICE001",
                    help="Format: 1-6 letters followed by 1-6 digits (e.g. RICE001). Must exist in the product catalog.",
                )
                waste_date_input = st.date_input(
                    "Waste Date *",
                    value=date.today(),
                    max_value=date.today(),
                    help="Cannot be a future date.",
                )
                quantity = st.number_input(
                    "Quantity Wasted (kg) *",
                    min_value=0.001,
                    max_value=float(MAX_QUANTITY_KG),
                    value=0.001,
                    step=0.1,
                    format="%.3f",
                    help=f"Must be greater than 0. Maximum: {MAX_QUANTITY_KG:,} kg.",
                )

            with col2:
                waste_reason = st.selectbox(
                    "Waste Reason *",
                    options=["-- Select a reason --"] + VALID_WASTE_REASONS,
                    help="Select the reason for waste.",
                )
                price_per_kg = st.number_input(
                    "Price per kg (Rs.) *",
                    min_value=0.01,
                    max_value=float(MAX_PRICE_PER_KG),
                    value=0.01,
                    step=1.0,
                    format="%.2f",
                    help=f"Must be greater than 0. Maximum: Rs. {MAX_PRICE_PER_KG:,}.",
                )
                estimated_loss = quantity * price_per_kg
                st.markdown(f"**Estimated Loss: {format_lkr(estimated_loss)}**")

            submitted = st.form_submit_button("Save Waste Record", use_container_width=True)

        if submitted:
            selected_reason = waste_reason if waste_reason != "-- Select a reason --" else ""
            errors = validate_waste_record_form(
                product_code, waste_date_input, quantity, selected_reason, price_per_kg
            )
            if errors:
                for err in errors:
                    st.error(err)
            else:
                with st.spinner("Verifying product code..."):
                    exists = product_code_exists(product_code.strip().upper())
                if not exists:
                    st.error(
                        f"Product code '{product_code.strip().upper()}' was not found "
                        "in the product catalog. Please check and try again."
                    )
                else:
                    with st.spinner("Saving record..."):
                        ok, msg = insert_waste_record(
                            product_code, waste_date_input,
                            quantity, selected_reason, estimated_loss,
                        )
                    if ok:
                        st.cache_data.clear()
                        st.success(f"Waste record for **{product_code.strip().upper()}** saved successfully.")
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.error(msg)

    st.divider()

    waste_df = fetch_waste_records(start, end)

    if waste_df.empty:
        st.info("No waste records found for the selected period.")
        return

    k1, k2, k3 = st.columns(3)
    with k1: st.metric("Total Waste",         f"{waste_df['quantity_wasted'].sum():,.2f} kg")
    with k2: st.metric("Total Financial Loss", format_lkr(waste_df["estimated_loss"].sum()))
    with k3:
        avg_daily = waste_df.groupby("waste_date")["quantity_wasted"].sum().mean()
        st.metric("Average Daily Waste", f"{avg_daily:.2f} kg")

    st.divider()

    ch1, ch2 = st.columns(2)

    with ch1:
        st.subheader("Waste Trend Over Time")
        daily = waste_df.groupby("waste_date")["quantity_wasted"].sum().reset_index()
        fig   = px.line(daily, x="waste_date", y="quantity_wasted",
                        markers=True, color_discrete_sequence=["#2563eb"])
        fig.update_layout(xaxis_title="Date", yaxis_title="Quantity (kg)",
                          margin=dict(t=10, b=30, l=30, r=10))
        st.plotly_chart(fig, use_container_width=True)

    with ch2:
        st.subheader("Top 10 Products by Waste")
        top10 = waste_df.groupby("product_code")["quantity_wasted"].sum().nlargest(10).reset_index()
        fig   = px.bar(top10, x="product_code", y="quantity_wasted",
                       color_discrete_sequence=["#2563eb"])
        fig.update_layout(xaxis_title="Product Code", yaxis_title="Total Waste (kg)",
                          margin=dict(t=10, b=40, l=30, r=10))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Waste Records")
    display = waste_df[
        ["waste_date", "product_code", "quantity_wasted",
         "waste_reason", "estimated_loss", "recorded_at"]
    ].copy()
    display["waste_date"]     = display["waste_date"].apply(fmt_date)
    display["estimated_loss"] = display["estimated_loss"].apply(format_lkr)
    display["recorded_at"]    = display["recorded_at"].apply(fmt_datetime)
    display.columns = ["Date", "Product", "Quantity (kg)", "Reason", "Est. Loss (Rs.)", "Recorded At"]

    st.dataframe(display, use_container_width=True, hide_index=True)

    csv = waste_df.to_csv(index=False)
    st.download_button(
        label="Export to CSV",
        data=csv,
        file_name=f"waste_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
