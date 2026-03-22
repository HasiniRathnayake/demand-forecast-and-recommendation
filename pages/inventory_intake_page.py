"""
pages/inventory_intake_page.py
==============================
Smart Inventory Intake page renderer.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.inventory_intake_repository import (
    fetch_ai_products,
    fetch_latest_forecast,
    fetch_recent_intake_logs,
    fetch_suppliers,
    save_intake_log,
)
from services.auth_service import get_current_user
from services.inventory_intake_service import SmartIntakeSystem, requires_remarks


def _inject_inventory_styles() -> None:
    st.markdown(
        """
        <style>
        /* Hide auto-discovered page navigation */
        [data-testid="stSidebarNav"] { display: none !important; }
        
        .ii-main-header {
            font-size: 2rem;
            font-weight: 700;
            color: #1D4ED8;
            margin-bottom: 0;
        }
        .ii-sub-header {
            font-size: 0.95rem;
            color: #64748B;
            margin-bottom: 1rem;
        }
        .ii-error-banner {
            background-color: #fee2e2;
            color: #b91c1c;
            padding: 1rem;
            border-radius: 10px;
            border-left: 6px solid #ef4444;
            margin-bottom: 0.75rem;
        }
        .ii-profile-badge {
            background-color: #DBEAFE;
            padding: 0.9rem;
            border-radius: 10px;
            margin-bottom: 0.75rem;
            border: 1px solid #BFDBFE;
        }
        .ii-profile-title {
            margin: 0;
            color: #1D4ED8;
            font-weight: 700;
            font-size: 1rem;
        }
        .ii-profile-text {
            margin: 0;
            color: #1E3A8A;
            font-size: 0.88rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    if "ii_step" not in st.session_state:
        st.session_state.ii_step = 1
    if "ii_temp_data" not in st.session_state:
        st.session_state.ii_temp_data = {}
    if "ii_items_scanned" not in st.session_state:
        st.session_state.ii_items_scanned = 0
    if "ii_anomalies_caught" not in st.session_state:
        st.session_state.ii_anomalies_caught = 0


def _render_sidebar() -> None:
    user = get_current_user() or {}
    display_name = (user.get("username") or "Operator").capitalize()
    staff_id = user.get("user_id", "N/A")

    with st.sidebar:
        st.markdown("### SUNRISE Super")
        st.caption("Warehouse Management System")
        st.divider()

        st.markdown(
            f"""
            <div class="ii-profile-badge">
                <p class="ii-profile-title">Operator Profile</p>
                <p class="ii-profile-text"><b>Name:</b> {display_name}</p>
                <p class="ii-profile-text"><b>Staff ID:</b> {staff_id}</p>
                <p class="ii-profile-text"><b>Role:</b> AI Intake Auditor</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Current Shift Metrics")
        col1, col2 = st.columns(2)
        col1.metric("Items Scanned", st.session_state.ii_items_scanned)
        col2.metric("Anomalies", st.session_state.ii_anomalies_caught)

        st.divider()
        if st.button("Reset Session", use_container_width=True):
            st.session_state.ii_items_scanned = 0
            st.session_state.ii_anomalies_caught = 0
            st.session_state.ii_step = 1
            st.session_state.ii_temp_data = {}
            st.rerun()


def _status_product_name(row: dict) -> str:
    product_obj = row.get("product_catalog")
    if isinstance(product_obj, dict):
        return product_obj.get("product_name") or "Unknown"
    if isinstance(product_obj, list) and product_obj:
        first = product_obj[0]
        if isinstance(first, dict):
            return first.get("product_name") or "Unknown"
    return "Unknown"


def _render_workflow_tab(system: SmartIntakeSystem) -> None:
    msg_spot = st.empty()
    suppliers = fetch_suppliers()
    ai_products = fetch_ai_products()

    if st.session_state.ii_step == 1:
        st.markdown("#### Step 1: Shipment Identification")
        st.info("Select incoming supplier and the AI-supported product.")

        col1, col2 = st.columns(2)
        vendor = col1.selectbox("Supplier", ["Select Supplier"] + list(suppliers.keys()), key="ii_supplier")
        product = col2.selectbox("Product", ["Select Product"] + list(ai_products.keys()), key="ii_product")

        if st.button("Proceed to Physical Count", type="primary", use_container_width=True):
            if vendor == "Select Supplier" or product == "Select Product":
                msg_spot.error("Please select both a valid supplier and product.")
            else:
                st.session_state.ii_temp_data = {
                    "supplier": vendor,
                    "supplier_id": suppliers[vendor],
                    "product": product,
                    "product_code": ai_products[product],
                }
                st.session_state.ii_step = 2
                st.rerun()

    elif st.session_state.ii_step == 2:
        product_name = st.session_state.ii_temp_data.get("product", "Selected product")
        p_code = st.session_state.ii_temp_data.get("product_code", "")
        forecast_id, ai_qty = fetch_latest_forecast(p_code)

        st.markdown(f"#### Step 2: Validate {product_name}")
        st.info(f"AI forecasted demand: {ai_qty:.2f} units.")

        with st.form("ii_entry_form"):
            actual = st.number_input("Enter Actual Physical Count", min_value=0.0, step=1.0)
            remarks = st.text_area(
                "Variance Remarks (required when anomaly is detected)",
                placeholder="Explain discrepancies, damages, or shortages...",
            )

            left, right = st.columns(2)
            back_clicked = left.form_submit_button("Change Item")
            save_clicked = right.form_submit_button("Validate and Save")

            if back_clicked:
                st.session_state.ii_step = 1
                st.rerun()

            if save_clicked:
                is_anomaly, msg, _severity = system.detect_anomaly(ai_qty, actual)

                if requires_remarks(is_anomaly, remarks):
                    msg_spot.warning(
                        "An anomaly was detected. Please provide at least 5 characters in remarks for audit trail."
                    )
                    return

                st.session_state.ii_items_scanned += 1
                if is_anomaly:
                    st.session_state.ii_anomalies_caught += 1
                    msg_spot.markdown(
                        f'<div class="ii-error-banner"><b>ANOMALY BLOCKED:</b> {msg}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    msg_spot.success(f"Match verified: {msg}")

                current_user = get_current_user() or {}
                payload = {
                    "supplier_id": st.session_state.ii_temp_data.get("supplier_id"),
                    "product_code": p_code,
                    "forecast_id": forecast_id,
                    "staff_id": str(current_user.get("user_id", "")),
                    "expected_qty": float(ai_qty),
                    "actual_qty": float(actual),
                    "is_anomaly": bool(is_anomaly),
                    "remarks": remarks,
                }

                if save_intake_log(payload):
                    st.toast("Record synced to database.")
                    st.session_state.ii_step = 1
                    st.session_state.ii_temp_data = {}
                else:
                    msg_spot.error("Failed to save intake record. Please retry.")


def _render_analytics_tab() -> None:
    st.markdown("#### System Audit Trail and Anomalies")

    rows = fetch_recent_intake_logs(limit=20)
    if not rows:
        st.info("No intake records found.")
        return

    chart_data = []
    for row in rows:
        chart_data.append(
            {
                "Timestamp": pd.to_datetime(row.get("created_at")).strftime("%Y-%m-%d %H:%M"),
                "Product": _status_product_name(row),
                "AI Expected": float(row.get("expected_qty") or 0.0),
                "Physical Count": float(row.get("actual_qty") or 0.0),
                "Status": "Anomaly" if row.get("is_anomaly") else "Verified",
            }
        )

    df = pd.DataFrame(chart_data)

    search_query = st.text_input("Filter logs by product name")
    if search_query:
        df = df[df["Product"].str.contains(search_query, case=False, na=False)]

    if df.empty:
        st.info("No rows match your filter.")
        return

    st.caption("Bar chart compares AI forecasted quantity and physical count.")
    st.bar_chart(df.set_index("Product")[["AI Expected", "Physical Count"]])
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_inventory_intake() -> None:
    _inject_inventory_styles()
    _init_state()

    st.markdown('<div class="ii-main-header">Smart Inventory Intake</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ii-sub-header">AI-assisted intake validation and anomaly audit trail</div>',
        unsafe_allow_html=True,
    )

    _render_sidebar()

    system = SmartIntakeSystem()
    tab1, tab2 = st.tabs(["Delivery Entry Workflow", "Real-Time Analytics Dashboard"])

    with tab1:
        _render_workflow_tab(system)
    with tab2:
        _render_analytics_tab()
