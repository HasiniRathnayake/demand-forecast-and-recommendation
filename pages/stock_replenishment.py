import streamlit as st
import requests
import pandas as pd

from config.settings import SUPABASE_URL, SUPABASE_KEY
from ui.styles import inject_styles

TABLE_REPLENISHMENT = "replenishment_orders"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# --- Supabase Fetchers ---
def fetch_orders():
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?select=*&order=created_at.desc"
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []

def fetch_products():
    url = f"{SUPABASE_URL}/rest/v1/product_catalog?select=product_code,product_name"
    resp = requests.get(url, headers=HEADERS)
    return {p["product_code"]: p.get("product_name", "Unknown") for p in resp.json()} if resp.status_code == 200 else {}

def fetch_suppliers():
    url = f"{SUPABASE_URL}/rest/v1/suppliers?select=*&order=supplier_name.asc"
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []

def fetch_purchase_orders():
    url = f"{SUPABASE_URL}/rest/v1/purchase_orders?select=*,suppliers(supplier_name),replenishment_orders(product_code,suggested_qty)&order=created_at.desc"
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []

# --- Mutations ---
def update_order_status(order_id, status, supplier_id=None, final_qty=None):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?order_id=eq.{order_id}"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}
    
    payload = {"status": status}
    if final_qty is not None:
        payload["suggested_qty"] = final_qty
        
    resp = requests.patch(url, headers=req_headers, json=payload)
    
    if resp.status_code in [200, 204]:
        if status == 'APPROVED' and supplier_id:
            po_url = f"{SUPABASE_URL}/rest/v1/purchase_orders"
            requests.post(po_url, headers=req_headers, json={
                "replenishment_order_id": order_id,
                "supplier_id": supplier_id,
                "status": "PENDING_DISPATCH"
            })
        st.toast(f"Order {order_id} marked as {status}!", icon="✅")
    else:
        st.error("Failed to update status.")

def save_override_log(order_id, code, predicted, ordered, reason):
    user = st.session_state.get("user", {})
    username = user.get("username", "Unknown Admin").capitalize()
    
    url = f"{SUPABASE_URL}/rest/v1/override_logs"
    resp = requests.post(url, headers=HEADERS, json={
        "order_id": order_id,
        "product_code": code,
        "predicted_quantity": predicted,
        "ordered_quantity": ordered,
        "anomaly_flag": True,
        "override_reason": reason,
        "overridden_by": username
    })
    if resp.status_code not in [200, 201]:
        st.error(f"Failed to save override log. ({resp.status_code})")

def _commit_override(order_id, code, predicted, ordered, supplier_id, reason):
    save_override_log(order_id, code, predicted, ordered, reason)
    update_order_status(order_id, 'APPROVED', supplier_id, final_qty=ordered)
    st.session_state.pop("pending_override", None)
    st.session_state.pop("override_reason_inline", None)
    st.rerun()


if hasattr(st, "dialog"):
    @st.dialog("⚠️ Anomaly Detected: Quantity Override")
    def _override_confirmation_dialog(order_id, code, predicted, ordered, supplier_id):
        st.warning("This order quantity is **significantly outside** the ML-expected range. Are you sure you want to continue?")
        st.markdown(f"**Predicted:** {predicted} units — **Requested:** {ordered} units")

        reason = st.text_area("Reason for Override (Mandatory)", placeholder="Example: Expected seasonal demand spike...")

        rc1, rc2 = st.columns(2)
        if rc1.button("Cancel", use_container_width=True):
            st.rerun()
        if rc2.button("Yes, I am sure", type="primary", use_container_width=True):
            if not reason.strip():
                st.error("Please provide a reason to continue.")
            else:
                _commit_override(order_id, code, predicted, ordered, supplier_id, reason)


def override_confirmation_dialog(order_id, code, predicted, ordered, supplier_id):
    # Streamlit < 1.34 does not support st.dialog; fallback to inline confirm panel.
    if hasattr(st, "dialog"):
        _override_confirmation_dialog(order_id, code, predicted, ordered, supplier_id)
        return

    st.session_state["pending_override"] = {
        "order_id": order_id,
        "code": code,
        "predicted": predicted,
        "ordered": ordered,
        "supplier_id": supplier_id,
    }
    st.rerun()

def update_po_status(po_id, status):
    url = f"{SUPABASE_URL}/rest/v1/purchase_orders?po_id=eq.{po_id}"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}
    requests.patch(url, headers=req_headers, json={"status": status})
    st.rerun()

def delete_purchase_order(po_id, rep_order_id):
    # 1. Delete the generated Purchase Order
    url_po = f"{SUPABASE_URL}/rest/v1/purchase_orders?po_id=eq.{po_id}"
    requests.delete(url_po, headers=HEADERS)
    
    # 2. Revert the parent ML recommendation status to cancelled
    if rep_order_id:
        url_rep = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?order_id=eq.{rep_order_id}"
        req_headers = {**HEADERS, "Prefer": "return=minimal"}
        requests.patch(url_rep, headers=req_headers, json={"status": "CANCELLED"})
        
    st.toast("Order successfully canceled!", icon="🛑")
    st.rerun()

def save_supplier(supplier_id, name, email, phone):
    url = f"{SUPABASE_URL}/rest/v1/suppliers"
    req_headers = {**HEADERS, "Prefer": "return=resolution"}
    data = {"supplier_id": supplier_id, "supplier_name": name, "email": email, "contact_number": phone}
    resp = requests.post(url, headers=HEADERS, json=data)
    if resp.status_code == 409: # Conflict, so update
        requests.patch(f"{url}?supplier_id=eq.{supplier_id}", headers=req_headers, json=data)
    st.toast("Supplier saved successfully!", icon="✅")
    st.rerun()

def delete_supplier(supplier_id):
    url = f"{SUPABASE_URL}/rest/v1/suppliers?supplier_id=eq.{supplier_id}"
    requests.delete(url, headers=HEADERS)
    st.toast("Supplier removed!", icon="🗑️")
    st.rerun()

# --- UI Renderer ---
def render_stock_replenishment():
    inject_styles()
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY in your environment.")
        return

    st.markdown("""
        <style>
        .badge { display: inline-block; padding: 0.25em 0.6em; font-size: 0.75rem; font-weight: 700; border-radius: 99px; text-align: center; }
        .bg-pending { background-color: rgba(245, 158, 11, 0.15); color: #d97706; border: 1px solid #fcd34d; }
        .bg-approved { background-color: rgba(5, 150, 105, 0.15); color: #059669; border: 1px solid #34d399; }
        .bg-rejected { background-color: rgba(220, 38, 38, 0.15); color: #dc2626; border: 1px solid #f87171; }
        .stock-critical { color: #ef4444; font-weight: 900; background: #fee2e2; padding: 2px 6px; border-radius: 4px;}
        .stock-low { color: #f59e0b; font-weight: bold; }
        .stock-ok { color: #10b981; }
        </style>
    """, unsafe_allow_html=True)

    with st.spinner("Loading ML pipeline and database records..."):
        orders = fetch_orders()
        catalog_map = fetch_products()
        suppliers = fetch_suppliers()
        pos = fetch_purchase_orders()
        default_supplier_id = suppliers[0]['supplier_id'] if suppliers else None

    # Inline fallback panel for older Streamlit versions without st.dialog.
    pending_override = st.session_state.get("pending_override")
    if pending_override and not hasattr(st, "dialog"):
        st.warning("⚠️ Anomaly Detected: Quantity Override")
        st.markdown(
            f"**Predicted:** {pending_override['predicted']} units — "
            f"**Requested:** {pending_override['ordered']} units"
        )
        reason = st.text_area(
            "Reason for Override (Mandatory)",
            placeholder="Example: Expected seasonal demand spike...",
            key="override_reason_inline",
        )
        rc1, rc2 = st.columns(2)
        if rc1.button("Cancel Override", use_container_width=True):
            st.session_state.pop("pending_override", None)
            st.session_state.pop("override_reason_inline", None)
            st.rerun()
        if rc2.button("Confirm Override", type="primary", use_container_width=True):
            if not reason.strip():
                st.error("Please provide a reason to continue.")
            else:
                _commit_override(
                    pending_override["order_id"],
                    pending_override["code"],
                    pending_override["predicted"],
                    pending_override["ordered"],
                    pending_override["supplier_id"],
                    reason,
                )

    import hashlib
    def get_fallback_name(sku):
        items = ["Organic Greek Yogurt", "Fresh Almond Milk", "Premium Whole Wheat Bread", "Cheddar Cheese Block", 
                 "Extra Virgin Olive Oil", "Himalayan Pink Salt", "Roasted Arabica Coffee", "Green Tea Bags",
                 "Free Range Eggs (Dozen)", "Sweet Red Apples", "Avocados", "Spaghetti Pasta 500g", 
                 "Tomato Basil Sauce", "Natural Peanut Butter", "Rolled Oats 1kg", "Wild Caught Salmon", 
                 "Chicken Breast Fillets", "Basmati Rice 5kg", "Frozen Mixed Berries", "Dark Chocolate 70%",
                 "Raw Honey 500g", "Mineral Water", "Roasted Almonds 200g", "Axe Body Spray", "Colgate Toothpaste",
                 "Nescafe Gold Blend", "Tropicana Orange Juice", "Lays Classic Potato Chips", "Oreo Cookies",
                 "Nutella Hazelnut Spread", "Gillette Mach3 Razor", "Head & Shoulders Shampoo"]
        idx = int(hashlib.md5(sku.encode()).hexdigest()[:6], 16) % len(items)
        return items[idx]

    # Main Tabs
    tab_dash, tab_po, tab_sup, tab_shrink = st.tabs([
        "📊 ML Dashboard & Approvals",
        "📦 Purchase Orders (Auto-POs)",
        "🏢 Supplier Directory",
        "📉 Shrinkage Analysis",
    ])

    # ─────────────────────────────────────────────────────────────────
    # TAB 1: ML Replenishment Dashboard
    # ─────────────────────────────────────────────────────────────────
    with tab_dash:
        if not orders:
            st.info("No replenishment orders found. Run ML pipeline.")
            return

    for o in orders:
       if o.get("product_name") in ["UNKNOWN PRODUCT", None, ""]:
        code = o.get("product_code", "UNKNOWN")
        # Try the actual product_catalog mapping first, then gracefully degrade to the consistent mock name
        o["product_name"] = catalog_map.get(code, get_fallback_name(code))

        pending_orders = [o for o in orders if o.get("status") == "PENDING_APPROVAL"]
        approved_orders = [o for o in orders if o.get("status") == "APPROVED"]
        rejected_orders = [o for o in orders if o.get("status") == "REJECTED"]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Pending Approval", len(pending_orders))
        col2.metric("Approved Orders", len(approved_orders))
        col3.metric("Total Units to Order", sum(o.get("suggested_qty", 0) for o in pending_orders))
        col4.metric("Pending Est. Value (KWD)", f"{sum(o.get('estimated_order_value_kwd', 0) for o in pending_orders):,.0f}")
            
        st.markdown("---")
        st.markdown("#### 🔴 Urgent Action Required: Critical Stockouts")
        def urgency_score(o):
            stock = o.get("current_stock_level", 0)
            reorder = max(o.get("reorder_point", 1), 1)
            return stock / reorder

        urgent_list = sorted(pending_orders, key=urgency_score)[:10]

        if urgent_list:
            h1, h2, h3, h4, h5, h6, h7 = st.columns([2.5, 1, 1, 1, 1, 2, 1])
            h1.caption("**Product**"); h2.caption("**Stock**"); h3.caption("**Reorder**")
            h4.caption("**Suggest Qty**"); h5.caption("**Logic**"); h6.caption("**Select Supplier**"); h7.caption("**Action**")

            # Pre-compute supplier names
            sup_map = {s['supplier_name']: s['supplier_id'] for s in suppliers}
            sup_list = list(sup_map.keys())

            for o in urgent_list:
                c1, c2, c3, c4, c5, c6, c7 = st.columns([2.5, 1, 1, 1, 1, 2, 1])
                c1.markdown(f"**{o.get('product_name')}**<br/><small>{o.get('product_code')}</small>", unsafe_allow_html=True)
                
                stock = o.get('current_stock_level', 0)
                reorder = o.get('reorder_point', 0)
                badge = f'<span class="stock-critical">{stock}</span>' if stock <= 0 else f'<span class="stock-low">{stock}</span>'
                c2.markdown(badge, unsafe_allow_html=True)
                
                c3.write(reorder)
                predicted_qty = int(o.get('suggested_qty', 1))
                with c4:
                    manual_qty = int(st.number_input("Qty", min_value=1, value=predicted_qty, step=1, key=f"qty_{o['order_id']}", label_visibility="collapsed"))
                
                with c5:
                    with st.popover("🧠"):
                        st.write(o.get('reasoning') or 'No reasoning')
                
                with c6:
                    selected_sup_name = st.selectbox("Supplier", options=sup_list, key=f"sel_{o['order_id']}", label_visibility="collapsed")
                    selected_sup_id = sup_map.get(selected_sup_name)

                with c7:
                    b1, b2 = st.columns(2)
                    if b1.button("✅", key=f"app_{o['order_id']}", help="Approve & Send to Supplier"):
                        if not selected_sup_id:
                            st.warning("Please add a supplier first!")
                        else:
                            # Anomaly Detection algorithm: >20% deviation OR >= 5 units absolute delta
                            deviation_pct = abs(manual_qty - predicted_qty) / max(predicted_qty, 1)
                            if deviation_pct > 0.20 or abs(manual_qty - predicted_qty) >= 5:
                                override_confirmation_dialog(o['order_id'], o.get('product_code'), predicted_qty, manual_qty, selected_sup_id)
                            else:
                                update_order_status(o['order_id'], 'APPROVED', selected_sup_id, final_qty=manual_qty)
                                st.rerun()
                    if b2.button("❌", key=f"rej_{o['order_id']}", help="Reject"):
                        update_order_status(o['order_id'], 'REJECTED')
                        st.rerun()
        else:
            st.success("🎉 No critical stockouts pending approval!")

        st.markdown("---")
        with st.expander("View All Processed Recommendations (History)"):
            all_df = pd.DataFrame([{
                "Product": o['product_name'], "SKU": o['product_code'],
                "Stock": o['current_stock_level'], "Qty": o['suggested_qty'],
                "Status": o['status']
            } for o in orders])
            st.dataframe(all_df, use_container_width=True)


    # ─────────────────────────────────────────────────────────────────
    # TAB 2: Purchase Orders
    # ─────────────────────────────────────────────────────────────────
    with tab_po:
        st.markdown("#### 📦 Generated Purchase Orders")
        if not pos:
            st.info("No purchase orders have been automatically generated yet. Approve an ML recommendation first.")
        else:
            h1, h2, h3, h4, h5 = st.columns([1.5, 2.5, 3, 1.5, 2.5])
            h1.caption("**Order ID**")
            h2.caption("**🏢 Supplier**")
            h3.caption("**📦 Item & Quantity**")
            h4.caption("**Status**")
            h5.caption("**Action**")

            for p in pos:
                with st.container(border=True):
                    poc1, poc2, poc3, poc4, poc5 = st.columns([1.5, 2.5, 3, 1.5, 2.5])
                    
                    po_display_id = str(p.get('po_id', ''))[:8].upper()
                    poc1.markdown(f"**{po_display_id}**")
                    
                    sup_name = p.get('suppliers', {}).get('supplier_name', 'Unknown') if p.get('suppliers') else 'Unknown'
                    poc2.write(f"{sup_name}")
                    
                    # New: Product Details extracted from the join
                    rep = p.get('replenishment_orders') or {}
                    p_code = rep.get('product_code', 'UNKNOWN')
                    qty = rep.get('suggested_qty', 0)
                    p_name = catalog_map.get(p_code, get_fallback_name(p_code))
                    poc3.markdown(f"**{p_name}**<br/><small>{qty} units</small>", unsafe_allow_html=True)
                    
                    status = p.get('status')
                    if status == 'PENDING_DISPATCH':
                        poc4.markdown('<span class="badge bg-pending">Pending Dispatch</span>', unsafe_allow_html=True)
                    elif status == 'SENT':
                        poc4.markdown('<span class="badge bg-approved">Sent to Supplier</span>', unsafe_allow_html=True)
                    else:
                        poc4.markdown('<span class="badge" style="background:#dbeafe;color:#1e3a8a;">Delivered</span>', unsafe_allow_html=True)
                        
                    with poc5:
                        if status == 'PENDING_DISPATCH':
                            bc1, bc2 = st.columns(2)
                            if bc1.button("Send ✉️", key=f"send_{p['po_id']}", use_container_width=True, help="Mark as Sent to Supplier"):
                                update_po_status(p['po_id'], 'SENT')
                            if bc2.button("Cancel 🗑️", type="primary", key=f"del_{p['po_id']}", use_container_width=True, help="Permanently Delete Order"):
                                delete_purchase_order(p['po_id'], p.get('replenishment_order_id'))
                        elif status == 'SENT':
                            if st.button("Mark Delivered 📥", key=f"deliv_{p['po_id']}", use_container_width=True):
                                update_po_status(p['po_id'], 'DELIVERED')


    # ─────────────────────────────────────────────────────────────────
    # TAB 3: Supplier Directory
    # ─────────────────────────────────────────────────────────────────
    with tab_sup:
        st.markdown("#### 🏢 Supplier Management")
        
        # Add new form
        with st.expander("➕ Add / Update Supplier", expanded=False):
            with st.form("supplier_form"):
                sc1, sc2 = st.columns(2)
                s_id = sc1.text_input("Supplier ID (e.g. SUP-005)", max_chars=20)
                s_name = sc2.text_input("Supplier Name")
                s_email = sc1.text_input("Email Contact")
                s_phone = sc2.text_input("Phone Number")
                
                if st.form_submit_button("Save Supplier", type="primary"):
                    if s_id and s_name:
                        save_supplier(s_id, s_name, s_email, s_phone)
                    else:
                        st.error("Supplier ID and Name are required!")

        # Display Existing Suppliers
        if suppliers:
            st.markdown("##### Active Suppliers")
            for sup in suppliers:
                sid = sup['supplier_id']
                with st.container(border=True):
                    sc1, sc2, sc3 = st.columns([3, 4, 1])
                    sc1.markdown(f"**{sup['supplier_name']}**<br/><small>{sid}</small>", unsafe_allow_html=True)
                    sc2.write(f"📧 {sup.get('email') or 'N/A'}\n📞 {sup.get('contact_number') or 'N/A'}")
                    if sc3.button("Delete", key=f"del_sup_{sid}", type="secondary"):
                        delete_supplier(sid)
        else:
            st.info("No suppliers exist in the database.")

    # ─────────────────────────────────────────────────────────────────
    # TAB 4: Shrinkage Analysis (Inventory Intake Dashboard)
    # ─────────────────────────────────────────────────────────────────
    with tab_shrink:
        st.markdown("#### 📉 Shrinkage Analysis")
        st.caption("Inventory intake analytics view only (workflow form hidden).")

        try:
            from pages.inventory_intake_page import render_shrinkage_analytics_only

            render_shrinkage_analytics_only()
        except Exception as exc:
            st.error(f"Unable to load Inventory Intake dashboard: {exc}")
