from __future__ import annotations

from datetime import datetime

import pandas as pd
import requests
import streamlit as st

from config.settings import SUPABASE_KEY, SUPABASE_URL
from services.auth_service import get_current_user, require_auth

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def _fetch_supplier_logs(supplier_id: str):
    url = (
        f"{SUPABASE_URL}/rest/v1/supplier_po_logs"
        f"?select=*,purchase_orders(status),suppliers(supplier_name)"
        f"&supplier_id=eq.{supplier_id}"
        f"&order=email_sent_at.desc&limit=500"
    )
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


def _update_po_status(po_id: str, status: str) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/purchase_orders?po_id=eq.{po_id}"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}
    resp = requests.patch(url, headers=req_headers, json={"status": status})
    return resp.status_code in [200, 204]


def render_supplier_dashboard() -> None:
    require_auth(["supplier", "admin"])
    user = get_current_user() or {}
    supplier_id = user.get("supplier_id")

    st.markdown("#### 📨 Supplier Dashboard")
    st.caption("Track your orders and update delivery progress.")

    if not supplier_id:
        st.error("Your account is not linked to a supplier record. Contact admin.")
        return

    logs = _fetch_supplier_logs(supplier_id)
    if not logs:
        st.info("No orders found for your supplier account.")
        return

    table_df = pd.DataFrame([
        {
            "PO ID": str(row.get("po_id", ""))[:8].upper(),
            "Supplier": (row.get("suppliers") or {}).get("supplier_name", "Unknown"),
            "Product Code": row.get("product_code", "N/A"),
            "Quantity": row.get("quantity", 0),
            "Expected Delivery": row.get("expected_delivery_date", "N/A"),
            "Notes": row.get("notes") or "-",
            "Email Sent At": datetime.fromisoformat(row.get("email_sent_at", "")).strftime("%Y-%m-%d %H:%M") if row.get("email_sent_at") else "N/A",
            "Status": (row.get("purchase_orders") or {}).get("status", "SENT"),
        }
        for row in logs
    ])
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("##### Update Shipment Status")
    for row in logs[:20]:
        po_status = (row.get("purchase_orders") or {}).get("status", "SENT")
        if po_status == "SENT":
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                c1.write(f"PO **{str(row.get('po_id',''))[:8].upper()}** · {row.get('product_code','N/A')} · {row.get('quantity',0)} units")
                c2.write(f"Status: **{po_status}**")
                if c3.button("Sent to Delivery 🚚", key=f"supplier_ship_{row.get('log_id')}", use_container_width=True):
                    ok = _update_po_status(row.get("po_id"), "IN_TRANSIT")
                    if ok:
                        st.success("Marked as Sent to Delivery.")
                        st.rerun()
                    else:
                        st.error("Failed to update shipment status.")
