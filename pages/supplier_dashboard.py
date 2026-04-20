from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

from config.settings import SUPABASE_KEY, SUPABASE_URL
from services.auth_service import get_current_user, require_auth
from modules.short_shipment_detector.detectors import ShortShipmentDetector

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

def _fetch_active_pos(supplier_id: str):
    url = (
        f"{SUPABASE_URL}/rest/v1/purchase_orders"
        f"?select=*,replenishment_orders(product_code,suggested_qty)"
        f"&supplier_id=eq.{supplier_id}"
        f"&status=in.(PENDING_DISPATCH,SENT)"
        f"&order=created_at.desc"
    )
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []

def _fetch_all_pos(supplier_id: str):
    url = (
        f"{SUPABASE_URL}/rest/v1/purchase_orders"
        f"?select=*,replenishment_orders(product_code,suggested_qty)"
        f"&supplier_id=eq.{supplier_id}"
        f"&order=created_at.desc&limit=100"
    )
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []

def _update_stock_in_catalog(product_code: str, added_qty: int):
    # Try to fetch current stock snapshot from replenishment_orders
    url = f"{SUPABASE_URL}/rest/v1/replenishment_orders?select=order_id,current_stock_level&product_code=eq.{product_code}&order=created_at.desc&limit=1"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200 and resp.json():
        row = resp.json()[0]
        curr_stock = int(row.get("current_stock_level") or 0)
        new_stock = curr_stock + added_qty
        
        # In a real enterprise system, we would update the central inventory table here.
        # But since replenishment_orders holds the current_stock_level cache:
        patch_url = f"{SUPABASE_URL}/rest/v1/replenishment_orders?order_id=eq.{row['order_id']}"
        req_headers = {**HEADERS, "Prefer": "return=minimal"}
        requests.patch(patch_url, headers=req_headers, json={"current_stock_level": new_stock})
        return new_stock
    return None

def _log_anomaly_to_deliveries(po_id, supplier_id, product_code, ordered_qty, received_qty, delivery_date):
    # Sends anomaly to central deliveries table where Short-Shipment AI grades from
    url = f"{SUPABASE_URL}/rest/v1/deliveries"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}
    
    detector = ShortShipmentDetector()
    disc_qty, disc_pct, status = detector.calculate_discrepancy(ordered_qty, received_qty)
    
    # We create a dummy delivery wrapper
    data = {
        "invoice_number": f"INV-{po_id[:8].upper()}",
        "delivery_date": delivery_date.isoformat(),
        "supplier_id": supplier_id
    }
    resp = requests.post(url, headers={**HEADERS, "Prefer": "return=representation"}, json=data)
    if resp.status_code in [200, 201]:
        delivery_id = resp.json()[0].get("delivery_id")
        
        item_data = {
            "delivery_id": delivery_id,
            "product_code": product_code,
            "billed_quantity": ordered_qty,
            "received_quantity": received_qty
        }
        item_url = f"{SUPABASE_URL}/rest/v1/delivery_items"
        requests.post(item_url, headers=req_headers, json=item_data)

def _fetch_supplier_profile(supplier_id: str):
    url = f"{SUPABASE_URL}/rest/v1/suppliers?supplier_id=eq.{supplier_id}&limit=1"
    resp = requests.get(url, headers=HEADERS)
    return resp.json()[0] if resp.status_code == 200 and resp.json() else {}

def _fetch_supplier_products(supplier_id: str):
    url = f"{SUPABASE_URL}/rest/v1/supplier_product_map?select=product_code,product_catalog(product_name)&supplier_id=eq.{supplier_id}"
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []

def render_supplier_dashboard() -> None:
    require_auth(["supplier"])
    user = get_current_user() or {}
    supplier_id = user.get("supplier_id")

    st.markdown("#### 📨 Supplier Performance & Fulfillment Portal")
    st.caption("Manage fulfillment, update shipments, and monitor your enterprise metrics.")

    if not supplier_id:
        st.error("Your account is not linked to a supplier record. Contact administration.")
        return

    # ── Tabs Navigation ───────────────────────────────────────────────────────
    tab_fulfill, tab_profile, tab_history = st.tabs([
        "🚀 Fulfillment & Orders", 
        "🏢 My Supplier Profile",
        "📜 Delivery History"
    ])
    
    all_pos = _fetch_all_pos(supplier_id)

    # ─────────────────────────────────────────────────────────────────
    # TAB 1: Fulfillment & Orders
    # ─────────────────────────────────────────────────────────────────
    with tab_fulfill:
        # ── Performance Metrics ───────────────────────────────────────────────────
        if all_pos:
            total_delivered = sum(1 for po in all_pos if po.get("status") == "DELIVERED")
            total_orders = len(all_pos)
            fulfillment_score = (total_delivered / total_orders * 100) if total_orders > 0 else 0
            
            # Minimal mock calculation for Lead Time Accuracy
            lead_time_accuracy = 100.0  # Would use actual vs expected dates in production
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📦 Processed Orders", f"{total_orders}")
            with col2:
                st.metric("🏆 Fulfillment Score", f"{fulfillment_score:.1f}%", help="Ratio of delivered vs assigned orders")
            with col3:
                st.metric("⏱️ Lead Time Accuracy", f"{lead_time_accuracy:.1f}%")
            
            st.progress(fulfillment_score / 100, text="Overall Reliability Score")
            st.markdown("---")

        # ── Pending PO / Fulfillment Updates ──────────────────────────────────────
        st.markdown("##### 🚀 Action Required: Outbound Shipments")
        active_pos = _fetch_active_pos(supplier_id)
        
        if not active_pos:
            st.info("✅ All caught up! No pending shipments at this time.")
        else:
            # Show pending POs table
            table_df = pd.DataFrame([
                {
                    "PO Reference": str(row.get("po_id", ""))[:8].upper(),
                    "Product": (row.get("replenishment_orders") or {}).get("product_code", "N/A"),
                    "Qty Ordered": (row.get("replenishment_orders") or {}).get("suggested_qty", 0),
                    "Assigned Date": datetime.fromisoformat(row.get("created_at", "")).strftime("%Y-%m-%d"),
                    "Status": row.get("status", "SENT"),
                }
                for row in active_pos
            ])
            st.dataframe(table_df, use_container_width=True, hide_index=True)

            st.markdown("###### Update Order Delivery Status")
            for row in active_pos:
                po_id = row.get("po_id")
                po_ref = str(po_id)[:8].upper()
                rep = row.get("replenishment_orders") or {}
                product_code = rep.get("product_code", "Unknown")
                qty_ordered = int(rep.get("suggested_qty", 0))

                with st.expander(f"📦 Record Delivery for PO: {po_ref}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        received_qty = st.number_input(
                            "Actual Units Delivered",
                            min_value=0, max_value=qty_ordered*2, value=qty_ordered,
                            key=f"recv_{po_id}"
                        )
                    with c2:
                        delivery_date = st.date_input(
                            "Actual Delivery Date",
                            value=datetime.now(timezone.utc),
                            key=f"date_{po_id}"
                        )

                    if received_qty < qty_ordered:
                        st.warning(f"⚠️ Short-Shipment Detected: You are short by {qty_ordered - received_qty} units.")

                    if st.button("Mark as Delivered & Sync ✅", key=f"btn_{po_id}", use_container_width=True):
                        with st.spinner("Processing fulfillment..."):
                            # AI grading logging for Short Shipment
                            if received_qty != qty_ordered:
                                _log_anomaly_to_deliveries(
                                    po_id, supplier_id, product_code, qty_ordered, received_qty, delivery_date
                                )
                            
                            # Sync Central Inventory Logic
                            stk = _update_stock_in_catalog(product_code, received_qty)
                            
                            # Update PO Status
                            url = f"{SUPABASE_URL}/rest/v1/purchase_orders?po_id=eq.{po_id}"
                            req_headers = {**HEADERS, "Prefer": "return=minimal"}
                            resp = requests.patch(url, headers=req_headers, json={"status": "DELIVERED"})
                            
                            if resp.status_code in [200, 204]:
                                if stk is not None:
                                    st.success(f"Successfully marked as Delivered. Central inventory incremented.")
                                else:
                                    st.success(f"Successfully marked as Delivered.")
                                st.rerun()
                            else:
                                st.error("Operation failed. Contact Admin.")

    # ─────────────────────────────────────────────────────────────────
    # TAB 2: My Supplier Profile (Directory Integration)
    # ─────────────────────────────────────────────────────────────────
    with tab_profile:
        st.markdown("##### 🏢 Company Profile")
        st.caption("Information tracked by Sunrise Supermarket regarding your enterprise.")
        
        profile = _fetch_supplier_profile(supplier_id)
        if not profile:
            st.info("No profile details found for your ID.")
        else:
            with st.container(border=True):
                pc1, pc2 = st.columns(2)
                pc1.markdown(f"**Enterprise Name:** {profile.get('supplier_name', 'N/A')}")
                pc1.markdown(f"**Supplier ID:** {profile.get('supplier_id', 'N/A')}")
                pc2.markdown(f"**Email Contact:** {profile.get('email', 'N/A')}")
                pc2.markdown(f"**Phone Support:** {profile.get('contact_number', 'N/A')}")
                
        st.markdown("---")
        st.markdown("##### 📦 Assigned Supply Catalog")
        st.caption("Products you are registered to supply to Sunrise.")
        products = _fetch_supplier_products(supplier_id)
        
        if products:
            prod_df = pd.DataFrame([
                {
                    "Product Code": p.get("product_code"),
                    "Product Name": (p.get("product_catalog") or {}).get("product_name", "Unknown")
                }
                for p in products
            ])
            st.dataframe(prod_df, use_container_width=True, hide_index=True)
        else:
            st.info("You do not currently have any products assigned to your catalog.")

    # ─────────────────────────────────────────────────────────────────
    # TAB 3: Delivery History
    # ─────────────────────────────────────────────────────────────────
    with tab_history:
        st.markdown("##### 📜 Past Deliveries & Completed POs")
        if all_pos:
            completed_pos = [po for po in all_pos if po.get("status") == "DELIVERED"]
            if completed_pos:
                hist_df = pd.DataFrame([
                    {
                        "PO Reference": str(row.get("po_id", ""))[:8].upper(),
                        "Product": (row.get("replenishment_orders") or {}).get("product_code", "N/A"),
                        "Qty Ordered": (row.get("replenishment_orders") or {}).get("suggested_qty", 0),
                        "Completed Date": datetime.fromisoformat(row.get("created_at", "")).strftime("%Y-%m-%d"),
                        "Status": row.get("status"),
                    }
                    for row in completed_pos
                ])
                st.dataframe(hist_df, use_container_width=True, hide_index=True)
            else:
                st.info("No completed deliveries on record yet.")
        else:
            st.info("No historical orders found.")

    st.markdown(
        '<div class="footer" style="text-align:center;color:#64748B;font-size:0.85rem;margin-top:2rem">'
        'Sunrise Supermarket Enterprise Portal</div>',
        unsafe_allow_html=True,
    )