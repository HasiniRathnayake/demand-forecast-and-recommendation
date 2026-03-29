import streamlit as st
import requests
import pandas as pd
import math
from datetime import datetime, timezone, timedelta

from config.settings import SUPABASE_URL, SUPABASE_KEY
from ui.styles import inject_styles
from pages.stock_replenishment_helpers import (
    _commit_override,
    delete_purchase_order,
    delete_supplier,
    fetch_approval_logs,
    fetch_forecast_dates,
    fetch_orders,
    fetch_product_supplier_map,
    fetch_products,
    fetch_purchase_orders,
    fetch_replenishment_status,
    fetch_suppliers,
    override_confirmation_dialog,
    save_supplier,
    send_po_email,
    update_order_status,
    update_po_status,
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

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
        forecast_dates = fetch_forecast_dates()
        default_supplier_id = suppliers[0]['supplier_id'] if suppliers else None

    if not forecast_dates:
        st.warning("No demand forecasts found. Generate forecasts before using Stock Replenishment.")
        return

    selected_forecast_date = st.date_input(
        "Forecast Date",
        value=pd.to_datetime(forecast_dates[0]).date(),
        help="Stock replenishment suggestions are computed from demand_forecasts for the selected date.",
    )

    with st.expander("📣 Promotion Uplift Planner", expanded=False):
        st.caption("Use this when live POS is delayed. It increases forecast demand using expected campaign response.")
        p1, p2, p3 = st.columns(3)
        enable_promo_uplift = p1.checkbox("Apply promotion uplift", value=True)
        promo_buy_probability = p2.slider("Buy probability", min_value=0.0, max_value=1.0, value=0.25, step=0.05)
        promo_reach_ratio = p3.slider("Campaign reach", min_value=0.0, max_value=1.0, value=0.50, step=0.05)
        safety_buffer_pct = st.slider("Safety buffer %", min_value=0, max_value=60, value=15, step=5)

    promo_multiplier = (promo_buy_probability * promo_reach_ratio) if enable_promo_uplift else 0.0

    # No longer needed since we're reading directly from demand_forecasts
    # forecast_map = fetch_forecasts_for_date(...)

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
                st.error("Please provide a reason before confirming.")
            else:
                _commit_override(
                    pending_override["order_id"],
                    pending_override["code"],
                    pending_override["predicted"],
                    pending_override["ordered"],
                    pending_override["supplier_id"],
                    reason.strip(),
                    pending_override.get("order_context", {}),
                )

    # Main Tabs
    tab_dash, tab_po, tab_sup, tab_supplier_dash, tab_shrink = st.tabs([
        "📊 ML Dashboard & Approvals",
        "📦 Purchase Orders (Auto-POs)",
        "🏢 Supplier Directory",
        "📨 Supplier Dashboard",
        "📉 Shrinkage Analysis",
    ])

    # ─────────────────────────────────────────────────────────────────
    # TAB 1: ML Replenishment Dashboard
    # ─────────────────────────────────────────────────────────────────
    with tab_dash:
        if not orders:
            st.info("No forecast rows found for replenishment planning.")
            return

        selected_date_text = str(selected_forecast_date)
        
        # DEBUG: Show selected date and available data
        with st.expander("🔍 Debug Info", expanded=False):
            st.write(f"Selected date: {selected_date_text}")
            st.write(f"Total forecast rows: {len(orders)}")
            st.write(f"Catalog products: {len(catalog_map)}")
            
            # Check what product codes are in today's forecast
            today_forecasts = [o for o in orders if str(o.get("forecast_date")) == selected_date_text]
            st.write(f"Forecasts for {selected_date_text}: {len(today_forecasts)} rows")
            if today_forecasts:
                codes_in_forecast = [o.get("product_code") for o in today_forecasts]
                codes_in_catalog = [c for c in codes_in_forecast if c in catalog_map]
                st.write(f"  - In forecast: {codes_in_forecast}")
                st.write(f"  - In catalog: {codes_in_catalog}")
        
        candidate_order_ids = []
        for o in orders:
            code = o.get("product_code", "UNKNOWN")
            fdate = o.get("forecast_date")
            if code in catalog_map and str(fdate) == selected_date_text:
                candidate_order_ids.append(o.get("forecast_id") or f"{code}-{fdate}")

        repl_status_map = fetch_replenishment_status(candidate_order_ids)

        filtered_orders = []
        for o in orders:
            code = o.get("product_code", "UNKNOWN")
            fdate = o.get("forecast_date")

            if code not in catalog_map:
                continue
            if str(fdate) != selected_date_text:
                continue

            order_id = o.get("forecast_id") or f"{code}-{fdate}"
            existing = repl_status_map.get(order_id) or {}
            current_status = existing.get("status", "PENDING_APPROVAL")

            o["order_id"] = order_id
            o["product_name"] = catalog_map.get(code, f"Unknown ({code})")

            predicted_qty = max(1, int(round(float(o.get("predicted_demand", 1)))))
            promo_uplift_qty = int(round(predicted_qty * promo_multiplier))
            adjusted_demand = predicted_qty + promo_uplift_qty
            demand_with_buffer = int(math.ceil(adjusted_demand * (1 + (safety_buffer_pct / 100.0))))

            planning_stock = 1
            o["current_stock_level"] = planning_stock

            needed_qty = max(0, demand_with_buffer - planning_stock)
            if needed_qty <= 0:
                continue

            o["suggested_qty"] = int(existing.get("suggested_qty") or needed_qty)
            o["reorder_point"] = 1
            o["status"] = current_status
            o["predicted_qty_base"] = predicted_qty

            conf = o.get("confidence_level")
            conf_txt = f"{float(conf) * 100:.1f}%" if conf is not None else "N/A"
            model = o.get("model_version") or "N/A"
            o["reasoning"] = (
                f"Forecast {predicted_qty} on {fdate} | Promo uplift +{promo_uplift_qty} | "
                f"Safety buffer {safety_buffer_pct}% | model {model} | confidence {conf_txt}"
            )
            filtered_orders.append(o)

        pending_orders = [o for o in filtered_orders if o.get("status") == "PENDING_APPROVAL"]
        approved_orders = [o for o in filtered_orders if o.get("status") == "APPROVED"]
        rejected_orders = [o for o in filtered_orders if o.get("status") == "REJECTED"]
        
        # DEBUG: Show filtering details
        with st.expander("🔍 Filtering Details", expanded=False):
            st.write(f"After catalog filter: {len(candidate_order_ids)} items (in both forecast & catalog for selected date)")
            st.write(f"After needed_qty > 0 filter: {len(filtered_orders)} items")
            st.write(f"  - Pending: {len(pending_orders)}")
            st.write(f"  - Approved: {len(approved_orders)}")
            st.write(f"  - Rejected: {len(rejected_orders)}")
            
            if not filtered_orders and candidate_order_ids:
                st.warning("All items were filtered out! Check:")
                st.write("- Is promo_multiplier set too high?")
                st.write("- Is safety_buffer_pct too high?")
                st.write("- Are all products showing needed_qty <= 0?")
        
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
            sup_id_to_name = {s['supplier_id']: s['supplier_name'] for s in suppliers}
            sup_list = list(sup_map.keys())
            product_supplier_map = fetch_product_supplier_map()

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
                    preferred_sid = product_supplier_map.get(o.get('product_code'))
                    preferred_name = sup_id_to_name.get(preferred_sid)
                    default_index = sup_list.index(preferred_name) if preferred_name in sup_list else 0
                    selected_sup_name = st.selectbox(
                        "Supplier",
                        options=sup_list,
                        index=default_index,
                        key=f"sel_{o['order_id']}",
                        label_visibility="collapsed",
                    )
                    if preferred_name:
                        c6.caption(f"Auto-mapped: {preferred_name}")
                    selected_sup_id = sup_map.get(selected_sup_name)

                with c7:
                    b1, b2 = st.columns(2)
                    if b1.button("✅", key=f"app_{o['order_id']}", help="Approve & Send to Supplier"):
                        if not selected_sup_id:
                            st.warning("Please add a supplier first!")
                        else:
                            override_confirmation_dialog(
                                o['order_id'],
                                o.get('product_code'),
                                predicted_qty,
                                manual_qty,
                                selected_sup_id,
                                {
                                    "order_id": o.get("order_id"),
                                    "product_code": o.get("product_code"),
                                    "product_name": o.get("product_name"),
                                    "current_stock_level": o.get("current_stock_level"),
                                    "reorder_point": o.get("reorder_point"),
                                    "estimated_order_value_kwd": o.get("estimated_order_value_kwd"),
                                    "daily_sales_velocity": o.get("daily_sales_velocity"),
                                    "forecast_7day_demand": o.get("predicted_qty_base"),
                                    "reasoning": o.get("reasoning"),
                                },
                            )
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
            } for o in filtered_orders])
            st.dataframe(all_df, use_container_width=True)

        with st.expander("🔐 Approval Audit Log", expanded=False):
            logs = fetch_approval_logs(limit=100)
            if not logs:
                st.info("No approval records yet.")
            else:
                log_df = pd.DataFrame(logs)
                log_df = log_df.rename(columns={
                    "order_id": "Order ID",
                    "product_code": "SKU",
                    "predicted_quantity": "Predicted Qty",
                    "ordered_quantity": "Ordered Qty",
                    "anomaly_flag": "Changed Qty",
                    "override_reason": "Reason",
                    "overridden_by": "Approved By",
                    "overridden_at": "Approved At",
                })
                st.dataframe(log_df, use_container_width=True)


    # ─────────────────────────────────────────────────────────────────
    # TAB 2: Purchase Orders
    # ─────────────────────────────────────────────────────────────────
    with tab_po:
        st.markdown("#### 📦 Generated Purchase Orders")
        send_test_mode = st.toggle(
            "Test mode (send to .env test email)",
            value=False,
            help="On: send to .env test recipient. Off: send to supplier email saved in database.",
            key="po_send_test_mode",
        )
        if send_test_mode:
            st.caption("Email target: test recipient from .env")
        else:
            st.caption("Email target: supplier email from database")
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
                    sup_email = p.get('suppliers', {}).get('email', '') if p.get('suppliers') else ''
                    poc2.write(f"{sup_name}")
                    
                    # New: Product Details extracted from the join
                    rep = p.get('replenishment_orders') or {}
                    p_code = rep.get('product_code', 'UNKNOWN')
                    qty = rep.get('suggested_qty', 0)
                    p_name = catalog_map.get(p_code, f"Unknown Product ({p_code})")
                    poc3.markdown(f"**{p_name}**<br/><small>{qty} units</small>", unsafe_allow_html=True)
                    
                    status = p.get('status')
                    if status == 'PENDING_DISPATCH':
                        poc4.markdown('<span class="badge bg-pending">Pending Dispatch</span>', unsafe_allow_html=True)
                    elif status == 'SENT':
                        poc4.markdown('<span class="badge bg-approved">Email Sent</span>', unsafe_allow_html=True)
                    elif status == 'IN_TRANSIT':
                        poc4.markdown('<span class="badge" style="background:#dbeafe;color:#1e3a8a;">Sent to Delivery</span>', unsafe_allow_html=True)
                    else:
                        poc4.markdown('<span class="badge" style="background:#dbeafe;color:#1e3a8a;">Delivered</span>', unsafe_allow_html=True)
                        
                    with poc5:
                        if status == 'PENDING_DISPATCH':
                            default_eta = datetime.now().date() + timedelta(days=1)
                            max_eta = datetime.now().date() + timedelta(days=90)
                            eta = st.date_input(
                                "Expected Delivery",
                                value=default_eta,
                                min_value=datetime.now().date(),
                                max_value=max_eta,
                                key=f"eta_{p['po_id']}",
                                help="Select a delivery date between today and next 90 days.",
                            )
                            notes = st.text_input(
                                "Notes",
                                key=f"po_note_{p['po_id']}",
                                placeholder="Optional note",
                            )
                            bc1, bc2 = st.columns(2)
                            button_label = "Send Email ✉️" if send_test_mode else "Send to Supplier ✉️"
                            if bc1.button(button_label, key=f"send_{p['po_id']}", use_container_width=True):
                                today = datetime.now().date()
                                if eta < today:
                                    st.error("Expected delivery date cannot be in the past.")
                                elif eta > (today + timedelta(days=90)):
                                    st.error("Expected delivery date must be within 90 days.")
                                else:
                                    if send_po_email(p, catalog_map, eta, notes=notes, test_mode=send_test_mode):
                                        st.rerun()
                            if bc2.button("Cancel 🗑️", type="primary", key=f"del_{p['po_id']}", use_container_width=True, help="Permanently Delete Order"):
                                delete_purchase_order(p['po_id'], p.get('replenishment_order_id'))
                        elif status == 'SENT':
                            st.caption("Waiting supplier to mark Sent to Delivery")
                        elif status == 'IN_TRANSIT':
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
    # TAB 4: Supplier Dashboard (View Received POs)
    # ─────────────────────────────────────────────────────────────────
    with tab_supplier_dash:
        st.markdown("#### 📨 Supplier Order Portal")
        st.caption("Suppliers can track orders and mark them as Sent to Delivery.")
        
        # Fetch PO logs
        try:
            url_logs = f"{SUPABASE_URL}/rest/v1/supplier_po_logs?select=*,suppliers(supplier_name),purchase_orders(status)&order=email_sent_at.desc&limit=500"
            resp = requests.get(url_logs, headers=HEADERS)
            po_logs = resp.json() if resp.status_code == 200 else []
        except:
            po_logs = []
        
        if not po_logs:
            st.info("No purchase orders have been sent to suppliers yet.")
        else:
            # Filter options
            col_filter1, col_filter2 = st.columns(2)
            
            with col_filter1:
                # Get unique suppliers from logs
                unique_suppliers = sorted(
                    set((log.get('suppliers') or {}).get('supplier_name', 'Unknown') for log in po_logs)
                )
                filter_supplier = st.multiselect(
                    "Filter by Supplier",
                    options=unique_suppliers,
                    default=None if len(unique_suppliers) > 3 else unique_suppliers
                )
            
            with col_filter2:
                date_range = st.date_input(
                    "Filter by Date Range",
                    value=(datetime.now().date() - timedelta(days=30), datetime.now().date()),
                    format="YYYY-MM-DD"
                )
            
            # Apply filters
            filtered_logs = po_logs
            if filter_supplier:
                filtered_logs = [
                    log for log in filtered_logs
                    if (log.get('suppliers') or {}).get('supplier_name', 'Unknown') in filter_supplier
                ]
            
            if len(date_range) == 2:
                filtered_logs = [
                    log for log in filtered_logs
                    if datetime.fromisoformat(log.get('email_sent_at', '')).date() >= date_range[0]
                    and datetime.fromisoformat(log.get('email_sent_at', '')).date() <= date_range[1]
                ]
            
            # Display logs as table
            st.markdown("##### Sent Purchase Orders")
            
            if filtered_logs:
                df_logs = pd.DataFrame([
                    {
                        "PO ID": str(log.get('po_id', ''))[:8].upper(),
                        "Supplier": (log.get('suppliers') or {}).get('supplier_name', 'Unknown'),
                        "Product Code": log.get('product_code', 'N/A'),
                        "Quantity": log.get('quantity', 0),
                        "Expected Delivery": log.get('expected_delivery_date', 'N/A'),
                        "Notes": log.get('notes', '') or '-',
                        "Sent To": log.get('email_address', 'N/A'),
                        "Sent By": log.get('sent_by', 'Unknown'),
                        "Sent At": datetime.fromisoformat(log.get('email_sent_at', '')).strftime('%Y-%m-%d %H:%M') if log.get('email_sent_at') else 'N/A',
                        "Status": (log.get('purchase_orders') or {}).get('status', 'SENT')
                    }
                    for log in filtered_logs
                ])
                
                st.dataframe(df_logs, use_container_width=True, hide_index=True)
                
                # Summary metrics
                st.markdown("---")
                st.markdown("##### Summary")
                
                met_col1, met_col2, met_col3, met_col4 = st.columns(4)
                met_col1.metric("Total POs Sent", len(filtered_logs))
                met_col2.metric("Total Units", sum(log.get('quantity', 0) for log in filtered_logs))
                met_col3.metric("In Transit", sum(1 for log in filtered_logs if (log.get('purchase_orders') or {}).get('status') == 'IN_TRANSIT'))
                met_col4.metric("Delivered", sum(1 for log in filtered_logs if (log.get('purchase_orders') or {}).get('status') == 'DELIVERED'))
                
                # Expandable details
                st.markdown("---")
                for idx, log in enumerate(filtered_logs[:10]):  # Show top 10
                    with st.expander(f"📋 PO {str(log.get('po_id', ''))[:8].upper()} - {log.get('product_code', 'N/A')}"):
                        detail_col1, detail_col2 = st.columns(2)
                        po_status = (log.get('purchase_orders') or {}).get('status', 'SENT')
                        
                        with detail_col1:
                            st.write(f"**Supplier:** {(log.get('suppliers') or {}).get('supplier_name', 'Unknown')}")
                            st.write(f"**Supplier Email:** {log.get('email_address', 'N/A')}")
                            st.write(f"**Quantity:** {log.get('quantity', 0)} units")
                            st.write(f"**Expected Delivery:** {log.get('expected_delivery_date', 'N/A')}")
                        
                        with detail_col2:
                            st.write(f"**Sent By:** {log.get('sent_by', 'Unknown')}")
                            st.write(f"**Sent At:** {datetime.fromisoformat(log.get('email_sent_at', '')).strftime('%Y-%m-%d %H:%M:%S') if log.get('email_sent_at') else 'N/A'}")
                            st.write(f"**Tracking Status:** {po_status}")

                        if po_status == 'SENT':
                            if st.button("Sent to Delivery 🚚", key=f"ship_{log.get('log_id')}", use_container_width=True):
                                if update_po_status(log.get('po_id'), 'IN_TRANSIT', do_rerun=False):
                                    st.success("Marked as Sent to Delivery.")
                                    st.rerun()
                        
                        if log.get('notes'):
                            st.write(f"**Notes:** {log.get('notes', 'N/A')}")
                        else:
                            st.write("**Notes:** -")
            else:
                st.info("No purchase orders match the selected filters.")

    # ─────────────────────────────────────────────────────────────────
    # TAB 5: Shrinkage Analysis (Inventory Intake Dashboard)
    # ─────────────────────────────────────────────────────────────────
    with tab_shrink:
        st.markdown("#### 📉 Shrinkage Analysis")
        st.caption("Inventory intake analytics view only (workflow form hidden).")

        try:
            from pages.inventory_intake_page import render_shrinkage_analytics_only

            render_shrinkage_analytics_only()
        except Exception as exc:
            st.error(f"Unable to load Inventory Intake dashboard: {exc}")

    # Direct-send flow is used in Purchase Orders tab; preview modal removed.

