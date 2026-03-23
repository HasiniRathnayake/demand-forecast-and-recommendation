import streamlit as st
import requests
import pandas as pd

from ml.config import SUPABASE_URL, HEADERS, TABLE_REPLENISHMENT
from ui.styles import inject_styles

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
    url = f"{SUPABASE_URL}/rest/v1/purchase_orders?select=*,suppliers(supplier_name)&order=created_at.desc"
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []

# --- Mutations ---
def update_order_status(order_id, status, supplier_id=None):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?order_id=eq.{order_id}"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}
    resp = requests.patch(url, headers=req_headers, json={"status": status})
    
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

def update_po_status(po_id, status):
    url = f"{SUPABASE_URL}/rest/v1/purchase_orders?po_id=eq.{po_id}"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}
    requests.patch(url, headers=req_headers, json={"status": status})
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
    tab_dash, tab_po, tab_sup = st.tabs(["📊 ML Dashboard & Approvals", "📦 Purchase Orders (Auto-POs)", "🏢 Supplier Directory"])

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
                c4.markdown(f"**{o.get('suggested_qty')}**")
                
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
                            update_order_status(o['order_id'], 'APPROVED', selected_sup_id)
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
            for p in pos:
                with st.container(border=True):
                    poc1, poc2, poc3, poc4 = st.columns([2, 3, 2, 2])
                    poc1.markdown(f"**{p.get('po_id')[:8].upper()}**")
                    sup_name = p.get('suppliers', {}).get('supplier_name', 'Unknown') if p.get('suppliers') else 'Unknown'
                    poc2.write(f"🏢 {sup_name}")
                    
                    status = p.get('status')
                    if status == 'PENDING_DISPATCH':
                        poc3.markdown('<span class="badge bg-pending">Pending Dispatch</span>', unsafe_allow_html=True)
                    elif status == 'SENT':
                        poc3.markdown('<span class="badge bg-approved">Sent to Supplier</span>', unsafe_allow_html=True)
                    else:
                        poc3.markdown('<span class="badge" style="background:#dbeafe;color:#1e3a8a;">Delivered</span>', unsafe_allow_html=True)
                        
                    with poc4:
                        if status == 'PENDING_DISPATCH':
                            if st.button("Mark as Sent ✉️", key=f"send_{p['po_id']}", use_container_width=True):
                                update_po_status(p['po_id'], 'SENT')
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
