import streamlit as st
import requests
import pandas as pd

from ml.config import SUPABASE_URL, HEADERS, TABLE_REPLENISHMENT
from ui.styles import inject_styles

def fetch_orders():
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?select=*&order=created_at.desc"
    # Using count=exact or just return=representation handling isn't strictly needed for small lists,
    # but let's fetch up to 1000 for display
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    st.error(f"Failed to fetch data: {resp.status_code}")
    return []

def update_status(order_id, status):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?order_id=eq.{order_id}"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}
    resp = requests.patch(url, headers=req_headers, json={"status": status})
    if resp.status_code in [200, 204]:
        st.toast(f"Order {order_id} marked as {status}!", icon="✅")
    else:
        st.error(f"Failed to update {order_id}: {resp.text}")

def render_stock_replenishment():
    inject_styles()
    
    # Custom CSS for the pills and badges
    st.markdown("""
        <style>
        .badge {
            display: inline-block; padding: 0.25em 0.6em; font-size: 0.75rem; 
            font-weight: 700; border-radius: 99px; text-align: center; white-space: nowrap;
        }
        .bg-pending { background-color: rgba(245, 158, 11, 0.15); color: #d97706; border: 1px solid #fcd34d; }
        .bg-approved { background-color: rgba(5, 150, 105, 0.15); color: #059669; border: 1px solid #34d399; }
        .bg-rejected { background-color: rgba(220, 38, 38, 0.15); color: #dc2626; border: 1px solid #f87171; }
        
        .stock-critical { color: #ef4444; font-weight: bold; }
        .stock-low { color: #f59e0b; font-weight: bold; }
        .stock-ok { color: #10b981; }
        </style>
    """, unsafe_allow_html=True)

    with st.spinner("Fetching ML replenishment predictions..."):
        orders = fetch_orders()

    if not orders:
        st.info("No replenishment orders found. Run the ML pipeline to generate predictions.")
        return

    # Calculate KPIs
    pending_orders = [o for o in orders if o.get("status") == "PENDING_APPROVAL"]
    approved_orders = [o for o in orders if o.get("status") == "APPROVED"]
    rejected_orders = [o for o in orders if o.get("status") == "REJECTED"]
    
    total_units = sum(o.get("suggested_qty", 0) for o in orders)
    total_value = sum(o.get("estimated_order_value_kwd", 0) for o in orders)

    # 1. KPI Cards
    st.markdown("### Stock Replenishment Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Replenishments", len(orders))
    with col2:
        st.metric("Pending Approval", len(pending_orders))
    with col3:
        st.metric("Approved", len(approved_orders))
    with col4:
        st.metric("Total Units to Order", f"{total_units:,}")
    with col5:
        st.metric("Est. Value (KWD)", f"{total_value:,.0f}")
        
    st.markdown("---")

    # Helper function to get row color class based on stock level
    def get_stock_html(stock, reorder):
        if stock == 0: return f'<span class="stock-critical">{stock}</span>'
        if stock <= reorder: return f'<span class="stock-low">{stock}</span>'
        return f'<span class="stock-ok">{stock}</span>'

    def get_status_html(status):
        if status == 'PENDING_APPROVAL': return '<span class="badge bg-pending">⏳ Pending</span>'
        if status == 'APPROVED': return '<span class="badge bg-approved">✅ Approved</span>'
        return '<span class="badge bg-rejected">❌ Rejected</span>'

    # 2. Top 10 Critical Stockouts (Pending, Urgent)
    st.markdown("#### 🔴 Top 10 Critical Stockouts *(Action Required)*")
    
    # Sort pending by stock/reorder ratio to find most critical
    def urgency_score(o):
        stock = o.get("current_stock_level", 0)
        reorder = max(o.get("reorder_point", 1), 1)
        return stock / reorder

    urgent_list = sorted(pending_orders, key=urgency_score)[:10]

    if urgent_list:
        # We will use st.container heavily here to mimic a table with action buttons
        # Header Row
        h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([1.5, 3, 1, 1, 1, 1, 1.5, 1.5])
        h1.caption("**Order ID**")
        h2.caption("**Product**")
        h3.caption("**SKU**")
        h4.caption("**Stock**")
        h5.caption("**Reorder**")
        h6.caption("**Suggest Qty**")
        h7.caption("**ML Reasoning**")
        h8.caption("**Action**")

        for o in urgent_list:
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.5, 3, 1, 1, 1, 1, 1.5, 1.5])
            c1.markdown(f"`{o.get('order_id')}`")
            c2.write(o.get('product_name'))
            c3.write(o.get('product_code'))
            c4.markdown(get_stock_html(o.get('current_stock_level', 0), o.get('reorder_point', 0)), unsafe_allow_html=True)
            c5.write(o.get('reorder_point'))
            c6.markdown(f"**{o.get('suggested_qty')}**")
            
            with c7:
                with st.popover("🧠 View Logic"):
                    st.write(o.get('reasoning') or 'No reasoning provided.')
            
            with c8:
                c8_1, c8_2 = st.columns(2)
                if c8_1.button("✅", key=f"urg_app_{o['order_id']}", help="Approve"):
                    update_status(o['order_id'], 'APPROVED')
                    st.rerun()
                if c8_2.button("❌", key=f"urg_rej_{o['order_id']}", help="Reject"):
                    update_status(o['order_id'], 'REJECTED')
                    st.rerun()
    else:
        st.success("🎉 No critical stockouts pending approval!")

    st.markdown("---")

    # 3. All Orders Data Tables
    st.markdown("#### All ML Suggestions")
    
    tab_pend, tab_app, tab_rej = st.tabs([
        f"⏳ Pending ({len(pending_orders)})", 
        f"✅ Approved ({len(approved_orders)})", 
        f"❌ Rejected ({len(rejected_orders)})"
    ])

    def render_data_editor(data_list, context):
        if not data_list:
            st.info(f"No {context} orders.")
            return

        # Prepare a flat list of dict for the dataframe
        df_list = []
        for o in data_list:
            df_list.append({
                "Order ID": o.get("order_id"),
                "Product": o.get("product_name"),
                "SKU": o.get("product_code"),
                "Stock": o.get("current_stock_level"),
                "Reorder Pts": o.get("reorder_point"),
                "Suggested Qty": o.get("suggested_qty"),
                "Value (KWD)": o.get("estimated_order_value_kwd"),
                "ML Reasoning": o.get("reasoning")[:80] + "..." if o.get("reasoning") else "",
            })
        
        df = pd.DataFrame(df_list)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_pend:
        # Instead of just a dataframe, we want to allow mass approval for pending
        st.caption("Select rows below if you wish to apply actions in bulk (not implemented in view-only dataframe).")
        # For simplicity in this demo, render the dataframe, and provide a single bulk approve button
        if pending_orders:
            if st.button("✅ Approve All Pending Orders", type="primary"):
                for o in pending_orders:
                    update_status(o['order_id'], 'APPROVED')
                st.rerun()
        render_data_editor(pending_orders, "pending")

    with tab_app:
        render_data_editor(approved_orders, "approved")

    with tab_rej:
        render_data_editor(rejected_orders, "rejected")
