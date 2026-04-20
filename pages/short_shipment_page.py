# pages/short_shipment_page.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import numpy as np
import smtplib
from email.mime.text import MIMEText
from ui.styles import inject_styles, render_page_heading
from modules.short_shipment_detector.database import get_db_connection


# =========================================================
# SUPABASE HELPERS
# =========================================================

def get_conn():
    return get_db_connection()


def get_suppliers():
    try:
        conn = get_conn()
        res = conn.table("suppliers").select("supplier_id, supplier_name, email").order("supplier_name").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching suppliers: {e}")
        return pd.DataFrame()


def get_products():
    try:
        conn = get_conn()
        res = conn.table("product_catalog").select("product_code, product_name, category, unit_price").order("product_name").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching products: {e}")
        return pd.DataFrame()


def get_pending_purchase_orders():
    """Fetch pending POs from Supabase"""
    try:
        conn = get_conn()

        po_res = conn.table("purchase_orders") \
            .select("po_id, replenishment_order_id, supplier_id, status") \
            .neq("status", "DELIVERED") \
            .execute()

        if not po_res.data:
            return pd.DataFrame()

        df = pd.DataFrame(po_res.data).drop_duplicates(subset=["po_id"])

        # Join suppliers
        sup_res = conn.table("suppliers").select("supplier_id, supplier_name, email").execute()
        if sup_res.data:
            sup_df = pd.DataFrame(sup_res.data)
            df = df.merge(sup_df, on="supplier_id", how="left")
            df["supplier_name"] = df["supplier_name"].fillna("Unknown")
            df["email"] = df["email"].fillna("")
        else:
            df["supplier_name"] = "Unknown"
            df["email"] = ""

        # Join replenishment_orders
        rep_ids = df["replenishment_order_id"].dropna().tolist()
        if rep_ids:
            rep_res = conn.table("replenishment_orders") \
                .select("order_id, product_code, suggested_qty") \
                .in_("order_id", rep_ids) \
                .execute()

            if rep_res.data:
                rep_df = pd.DataFrame(rep_res.data)
                rep_df.rename(columns={"order_id": "replenishment_order_id", "suggested_qty": "ordered_qty"}, inplace=True)
                df = df.merge(rep_df, on="replenishment_order_id", how="left")
                df["ordered_qty"] = df["ordered_qty"].fillna(0)

                # Join product names
                product_codes = df["product_code"].dropna().unique().tolist()
                if product_codes:
                    prod_res = conn.table("product_catalog") \
                        .select("product_code, product_name") \
                        .in_("product_code", product_codes) \
                        .execute()
                    if prod_res.data:
                        prod_df = pd.DataFrame(prod_res.data)
                        df = df.merge(prod_df, on="product_code", how="left")
                        df["product_name"] = df["product_name"].fillna("Unknown")
                    else:
                        df["product_name"] = "Unknown"
                else:
                    df["product_name"] = "Unknown"
            else:
                df["product_name"] = "Unknown"
                df["ordered_qty"] = 0
        else:
            df["product_name"] = "Unknown"
            df["ordered_qty"] = 0

        df["ordered_qty"] = df["ordered_qty"].fillna(0).astype(int)
        return df

    except Exception as e:
        st.error(f"Error fetching purchase orders: {e}")
        return pd.DataFrame()


def get_deliveries_for_reconciliation(start_date, end_date):
    """Fetches deliveries and handles missing products gracefully"""
    try:
        conn = get_conn()
        
        # Get deliveries in date range
        deliveries_res = conn.table("deliveries") \
            .select("delivery_id, invoice_number, delivery_date, supplier_id") \
            .gte("delivery_date", start_date.strftime("%Y-%m-%d")) \
            .lte("delivery_date", end_date.strftime("%Y-%m-%d")) \
            .execute()
        
        if not deliveries_res.data:
            return pd.DataFrame()
        
        # Get delivery items for these deliveries
        delivery_ids = [d['delivery_id'] for d in deliveries_res.data]
        items_res = conn.table("delivery_items") \
            .select("delivery_id, product_code, billed_quantity, received_quantity") \
            .in_("delivery_id", delivery_ids) \
            .execute()
        
        if not items_res.data:
            return pd.DataFrame()
        
        # Get supplier info
        supplier_ids = list(set([d['supplier_id'] for d in deliveries_res.data]))
        suppliers_res = conn.table("suppliers") \
            .select("supplier_id, supplier_name, email") \
            .in_("supplier_id", supplier_ids) \
            .execute()
        suppliers_dict = {s['supplier_id']: s for s in (suppliers_res.data or [])}
        
        # Get product info (handle missing products)
        product_codes = list(set([i['product_code'] for i in items_res.data]))
        products_res = conn.table("product_catalog") \
            .select("product_code, product_name, unit_price") \
            .in_("product_code", product_codes) \
            .execute()
        products_dict = {p['product_code']: p for p in (products_res.data or [])}
        
        # Track missing products for warning
        missing_products = set(product_codes) - set(products_dict.keys())
        if missing_products:
            st.warning(f"⚠️ Missing product codes in catalog: {', '.join(missing_products)}")
        
        # Build the data
        data = []
        for delivery in deliveries_res.data:
            supplier = suppliers_dict.get(delivery['supplier_id'], {})
            supplier_name = supplier.get('supplier_name', 'Unknown')
            supplier_email = supplier.get('email', '')
            
            # Find items for this delivery
            delivery_items = [i for i in items_res.data if i['delivery_id'] == delivery['delivery_id']]
            
            for item in delivery_items:
                product = products_dict.get(item['product_code'], {})
                
                # If product not found, use default values
                if not product:
                    product_name = f"Unknown ({item['product_code']})"
                    unit_price = 0
                else:
                    product_name = product.get('product_name', 'Unknown')
                    unit_price = float(product.get('unit_price', 0) or 0)
                
                billed = float(item.get('billed_quantity', 0))
                received = float(item.get('received_quantity', 0))
                disc_qty = received - billed
                disc_pct = (disc_qty / billed * 100) if billed > 0 else 0
                
                data.append({
                    'date': delivery.get('delivery_date'),
                    'invoice': delivery.get('invoice_number'),
                    'supplier': supplier_name,
                    'supplier_email': supplier_email,
                    'product': product_name,
                    'product_code': item.get('product_code'),
                    'ordered': billed,
                    'received': received,
                    'discrepancy_qty': disc_qty,
                    'discrepancy_pct': disc_pct,
                    'unit_price': unit_price,
                    'financial_impact': disc_qty * unit_price,
                    'status': 'Short' if disc_qty < 0 else 'Over' if disc_qty > 0 else 'Accurate',
                })
        
        return pd.DataFrame(data)
        
    except Exception as e:
        st.error(f"Error fetching reconciliation data: {e}")
        return pd.DataFrame()


def save_delivery_to_supabase(supplier_id, product_code, ordered_qty, received_qty, delivery_date):
    """Insert a delivery + delivery_item row into Supabase."""
    try:
        conn = get_conn()

        # Insert delivery header
        delivery_res = conn.table("deliveries").insert({
            "supplier_id": str(supplier_id),
            "invoice_number": f"DEL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "delivery_date": delivery_date.isoformat(),
        }).execute()

        if not delivery_res.data:
            return False, "deliveries insert returned no data"

        delivery_id = delivery_res.data[0]["delivery_id"]

        # Insert delivery item
        item_res = conn.table("delivery_items").insert({
            "delivery_id": str(delivery_id),
            "product_code": str(product_code),
            "billed_quantity": float(ordered_qty),
            "received_quantity": float(received_qty),
        }).execute()

        if not item_res.data:
            return False, "delivery_items insert returned no data"

        return True, None

    except Exception as e:
        return False, str(e)


def mark_po_delivered(po_id):
    """Mark a PO and its linked replenishment order as DELIVERED."""
    try:
        conn = get_conn()
        conn.table("purchase_orders").update({"status": "DELIVERED"}).eq("po_id", str(po_id)).execute()

        # Get replenishment_order_id for this PO
        po_row = conn.table("purchase_orders").select("replenishment_order_id").eq("po_id", str(po_id)).execute()
        if po_row.data and po_row.data[0].get("replenishment_order_id"):
            rep_id = po_row.data[0]["replenishment_order_id"]
            conn.table("replenishment_orders").update({"status": "DELIVERED"}).eq("order_id", str(rep_id)).execute()
    except Exception as e:
        st.warning(f"Could not mark PO as delivered: {e}")


def get_delivery_drafts():
    """Fetch saved drafts from Supabase delivery_drafts table."""
    try:
        conn = get_conn()
        res = conn.table("delivery_drafts") \
            .select("*") \
            .order("draft_id", desc=True) \
            .limit(50) \
            .execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching drafts: {e}")
        return pd.DataFrame()


def save_draft_to_supabase(supplier_name, product_name, ordered_qty, received_qty, delivery_date):
    """Save a draft row to Supabase delivery_drafts table."""
    try:
        conn = get_conn()
        disc_qty = float(received_qty) - float(ordered_qty)
        disc_pct = round((disc_qty / float(ordered_qty) * 100), 1) if float(ordered_qty) > 0 else 0.0

        conn.table("delivery_drafts").insert({
            "order_number": f"DRAFT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "supplier_name": str(supplier_name),
            "product_name": str(product_name),
            "ordered_quantity": float(ordered_qty),
            "received_quantity": float(received_qty),
            "discrepancy_quantity": float(disc_qty),
            "discrepancy_percentage": float(disc_pct),
            "delivery_date": str(delivery_date),
            "source_type": "manual",
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving draft: {e}")
        return False


def send_delivery_alert(supplier_name, product_name, ordered_qty, received_qty, discrepancy_qty, delivery_date, po_id=None):
    your_email = "hashiniwickramathilaka@gmail.com"
    sender_email = "hashiniwickramathilaka@gmail.com"
    sender_password = "egjososgumoiiqqs"

    if discrepancy_qty < 0:
        alert_type = "⚠️ SHORT SHIPPED"
        action_needed = f"Contact supplier for credit note — missing {abs(discrepancy_qty):,.0f} units"
    elif discrepancy_qty > 0:
        alert_type = "📦 OVER DELIVERED"
        action_needed = f"Review {discrepancy_qty:,.0f} extra units — return or negotiate"
    else:
        alert_type = "✅ ACCURATE DELIVERY"
        action_needed = "No action required — update inventory"

    pct = (abs(discrepancy_qty) / ordered_qty * 100) if ordered_qty > 0 else 0
    subject = f"{alert_type}: {supplier_name} - {product_name}"
    body = f"""
SUNRISE SUPERMARKET — DELIVERY STATUS REPORT

Alert:          {alert_type}
Date & Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Delivery Date:  {delivery_date}
PO Reference:   {po_id if po_id else 'Manual Entry'}

Supplier:       {supplier_name}
Product:        {product_name}
Ordered Qty:    {ordered_qty:,.0f} units
Received Qty:   {received_qty:,.0f} units
Variance:       {discrepancy_qty:+,.0f} units ({pct:+.1f}%)

Action:         {action_needed}

---
Automated alert from SUNRISE Supermarket Short-Shipment Detection System
"""
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = your_email
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def calculate_next_order_adjustment(rec_df):
    if rec_df.empty:
        return pd.DataFrame()

    summary = rec_df.groupby(["supplier", "product"]).agg(
        ordered=("ordered", "sum"),
        received=("received", "sum"),
        discrepancy_qty=("discrepancy_qty", "sum"),
        financial_impact=("financial_impact", "sum"),
    ).reset_index()

    rows = []
    for _, row in summary.iterrows():
        disc = row["discrepancy_qty"]
        if disc < 0:
            rows.append({
                "supplier": row["supplier"], "product": row["product"],
                "ordered": row["ordered"], "received": row["received"],
                "discrepancy_qty": disc,
                "adjustment_type": "Add to Next Order",
                "adjustment_qty": abs(disc),
                "financial_impact": row["financial_impact"],
                "reason": f"Short by {abs(disc):,.0f} units across deliveries",
            })
        elif disc > 0:
            rows.append({
                "supplier": row["supplier"], "product": row["product"],
                "ordered": row["ordered"], "received": row["received"],
                "discrepancy_qty": disc,
                "adjustment_type": "Credit for Next Order",
                "adjustment_qty": disc,
                "financial_impact": row["financial_impact"],
                "reason": f"Over by {disc:,.0f} units across deliveries",
            })
        else:
            rows.append({
                "supplier": row["supplier"], "product": row["product"],
                "ordered": row["ordered"], "received": row["received"],
                "discrepancy_qty": 0,
                "adjustment_type": "No Adjustment",
                "adjustment_qty": 0,
                "financial_impact": 0,
                "reason": "All deliveries accurate",
            })
    return pd.DataFrame(rows)


# =========================================================
# MAIN RENDER FUNCTION
# =========================================================

def render_short_shipment():
    inject_styles()
    render_page_heading("Short-Shipment Detector")
    st.divider()

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📦 Record Delivery", "📈 Discrepancy Trend Analyzer"])

    # =========================================================
    # TAB 1: DASHBOARD & ORDER RECONCILIATION
    # =========================================================
    with tab1:
        st.markdown('<div class="section-title">📊 Dashboard & Order Reconciliation</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            rec_start = st.date_input("📅 From Date", value=date.today() - timedelta(days=90), key="recon_start_date")
        with col2:
            rec_end = st.date_input("📅 To Date", value=date.today(), key="recon_end_date")

        rec_df = get_deliveries_for_reconciliation(rec_start, rec_end)

        if rec_df.empty:
            st.info("📭 No delivery data found for the selected period.")
        else:
            total_orders = rec_df["ordered"].sum()
            total_received = rec_df["received"].sum()
            total_shortage = rec_df[rec_df["discrepancy_qty"] < 0]["discrepancy_qty"].sum()
            total_financial_impact = rec_df["financial_impact"].sum()

            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            with col_s1:
                st.metric("📦 Total Ordered", f"{total_orders:,.0f} units")
            with col_s2:
                st.metric("✅ Total Received", f"{total_received:,.0f} units")
            with col_s3:
                st.metric("⚠️ Total Shortage", f"{abs(total_shortage):,.0f} units")
            with col_s4:
                st.metric("💰 Financial Impact", f"LKR {abs(total_financial_impact):,.2f}")

            st.markdown("---")
            st.markdown("#### 📊 Delivery Status Distribution")
            status_counts = rec_df["status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            status_map = {"Short": "⚠️ Short Shipped", "Over": "📦 Over Delivered", "Accurate": "✅ Accurate"}
            status_counts["Display Status"] = status_counts["Status"].map(status_map)
            fig = px.pie(
                status_counts, values="Count", names="Display Status",
                title="Delivery Status Distribution", hole=0.4,
                color_discrete_sequence=["#e74c3c", "#f39c12", "#2ecc71"],
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown("### 📋 Recommended Adjustments for Next Order")

            adjustments_df = calculate_next_order_adjustment(rec_df)

            if adjustments_df.empty:
                st.info("📭 No adjustments found.")
            else:
                display_df = adjustments_df.copy()
                display_df["ordered"] = display_df["ordered"].apply(lambda x: f"{x:,.0f}")
                display_df["received"] = display_df["received"].apply(lambda x: f"{x:,.0f}")
                display_df["discrepancy_qty"] = display_df["discrepancy_qty"].apply(lambda x: f"{x:+,.0f}")
                display_df["adjustment_qty"] = display_df["adjustment_qty"].apply(lambda x: f"{x:,.0f}")
                display_df.columns = [
                    "Supplier", "Product", "Ordered Qty", "Received Qty",
                    "Variance", "Adjustment Type", "Adjustment Qty", "Financial Impact", "Reason",
                ]
                st.dataframe(display_df, use_container_width=True, hide_index=True)

                csv_data = adjustments_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Adjustments as CSV",
                    data=csv_data,
                    file_name=f"adjustments_{date.today()}.csv",
                    mime="text/csv",
                    key="download_adjustments",
                )

    # =========================================================
    # TAB 2: RECORD DELIVERY WITH AUTO-FILL (LOCKED FIELDS)
    # =========================================================
    with tab2:
        st.markdown('<div class="section-title">📦 Record New Delivery</div>', unsafe_allow_html=True)

        # Fetch from Supabase using the helper functions
        suppliers_df = get_suppliers()
        products_df = get_products()

        if suppliers_df.empty or products_df.empty:
            st.warning("⚠️ Please add suppliers and products first in Supabase.")
            st.info("Go to Supabase dashboard → Table Editor → Add suppliers and products")
        else:
            st.success(f"✅ Found {len(suppliers_df)} suppliers and {len(products_df)} products")
            
            # Get pending POs
            pending_pos = get_pending_purchase_orders()
            
            # Initialize session state for auto-fill if not exists
            if 'selected_po_data' not in st.session_state:
                st.session_state.selected_po_data = None
            
            if not pending_pos.empty and 'po_id' in pending_pos.columns:
                st.info(f"📋 {len(pending_pos)} pending purchase orders from Replenishment System")
                
                # Create display options
                pending_pos['display'] = pending_pos.apply(
                    lambda row: f"📄 {str(row['po_id'])[:8]}... | 🏢 {row.get('supplier_name', 'Unknown')} | 📦 {row.get('product_name', 'Unknown')} | 🔢 Qty: {row.get('ordered_qty', 0)}",
                    axis=1
                )
                pending_pos = pending_pos.drop_duplicates(subset=['po_id'])
                
                # Add "None" option at the beginning
                po_options = ["-- Select a PO --"] + pending_pos['display'].tolist()
                selected_display = st.selectbox(
                    "🔽 Select Purchase Order (Auto-fill from Replenishment)", 
                    po_options,
                    key="po_selectbox"
                )
                
                if selected_display != "-- Select a PO --":
                    po_data = pending_pos[pending_pos['display'] == selected_display].iloc[0]
                    st.session_state.selected_po_data = {
                        'supplier_name': po_data.get('supplier_name', ''),
                        'product_name': po_data.get('product_name', ''),
                        'ordered_qty': int(po_data.get('ordered_qty', 0)),
                        'po_id': po_data.get('po_id'),
                        'supplier_id': po_data.get('supplier_id', '')
                    }
                else:
                    # Clear selection if "None" is chosen
                    if st.session_state.selected_po_data is not None:
                        st.session_state.selected_po_data = None
                        st.rerun()
            else:
                if st.session_state.selected_po_data is not None:
                    st.session_state.selected_po_data = None
            
            st.markdown("---")
            
            # Delivery Form
            col1, col2 = st.columns(2)
            
            # Check if PO is selected
            is_po_selected = st.session_state.selected_po_data is not None
            
            with col1:
                st.markdown("#### 🏢 Delivery Information")
                
                if is_po_selected:
                    # PO Selected - Show locked supplier field
                    supplier_name = st.session_state.selected_po_data['supplier_name']
                    supplier = st.text_input("Supplier *", value=supplier_name, disabled=True, key="supplier_locked")
                    
                    # Get supplier_id from the selected PO data
                    supplier_id = st.session_state.selected_po_data.get('supplier_id', '')
                    if not supplier_id:
                        # Fallback: get supplier_id from suppliers_df using supplier_name
                        supplier_row = suppliers_df[suppliers_df['supplier_name'] == supplier_name]
                        if not supplier_row.empty:
                            supplier_id = supplier_row.iloc[0]['supplier_id']
                else:
                    # No PO selected - Normal selectbox
                    supplier_list = suppliers_df['supplier_name'].tolist()
                    supplier = st.selectbox("Supplier *", supplier_list, key="supplier_select")
                    supplier_row = suppliers_df[suppliers_df['supplier_name'] == supplier]
                    supplier_id = supplier_row.iloc[0]['supplier_id'] if not supplier_row.empty else ''
                
                delivery_date = st.date_input("Delivery Date", value=date.today(), key="delivery_date")
            
            with col2:
                st.markdown("#### 📦 Product Information")
                
                if is_po_selected:
                    # PO Selected - Show locked product field
                    product_name = st.session_state.selected_po_data['product_name']
                    product = st.text_input("Product *", value=product_name, disabled=True, key="product_locked")
                    
                    # Get product_code from products_df
                    product_row = products_df[products_df['product_name'] == product_name]
                    product_code = product_row.iloc[0]['product_code'] if not product_row.empty else ''
                    
                    # Ordered quantity - Locked when PO is selected
                    ordered_qty = st.number_input(
                        "Ordered Quantity *", 
                        min_value=0, 
                        value=st.session_state.selected_po_data['ordered_qty'], 
                        step=10, 
                        key="ordered_qty_locked",
                        disabled=True
                    )
                else:
                    # No PO selected - Normal editable fields
                    product_list = products_df['product_name'].tolist()
                    product = st.selectbox("Product *", product_list, key="product_select")
                    product_row = products_df[products_df['product_name'] == product]
                    product_code = product_row.iloc[0]['product_code'] if not product_row.empty else ''
                    
                    ordered_qty = st.number_input(
                        "Ordered Quantity *", 
                        min_value=0, 
                        value=0, 
                        step=10, 
                        key="ordered_qty_editable"
                    )
                
                # Received Quantity - Always editable
                received_qty = st.number_input(
                    "Received Quantity *", 
                    min_value=0, 
                    value=0, 
                    step=10, 
                    key="received_qty"
                )
            
            # Calculate discrepancy
            if ordered_qty > 0 or received_qty > 0:
                disc_qty = received_qty - ordered_qty
                disc_pct = (disc_qty / ordered_qty * 100) if ordered_qty > 0 else 0
                
                st.markdown("---")
                st.markdown("#### 📊 Discrepancy Summary")
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Discrepancy", f"{disc_qty:+.0f} units")
                with col_b:
                    st.metric("Percentage", f"{disc_pct:+.1f}%")
                with col_c:
                    if disc_qty < 0:
                        st.metric("Status", "⚠️ Short Shipped")
                    elif disc_qty > 0:
                        st.metric("Status", "📦 Over Delivered")
                    else:
                        st.metric("Status", "✅ Accurate")
                
                # Email alert button
                if disc_qty != 0:
                    st.markdown("---")
                    st.markdown("#### 📧 Send Alert")
                    
                    col_email1, col_email2 = st.columns([3, 1])
                    with col_email1:
                        if disc_qty < 0:
                            st.warning(f"⚠️ Shortage detected: {abs(disc_qty)} units missing")
                        else:
                            st.info(f"📦 Over delivery detected: {disc_qty} extra units")
                    
                    with col_email2:
                        if st.button("📧 Send Email Alert", key="send_email_btn", use_container_width=True):
                            with st.spinner("Sending email..."):
                                email_sent = send_delivery_alert(
                                    supplier_name=supplier,
                                    product_name=product,
                                    ordered_qty=ordered_qty,
                                    received_qty=received_qty,
                                    discrepancy_qty=disc_qty,
                                    delivery_date=delivery_date.strftime('%Y-%m-%d'),
                                    po_id=st.session_state.selected_po_data['po_id'] if is_po_selected else 'N/A'
                                )
                                if email_sent:
                                    st.success(f"📧 Alert sent to your email!")
                                else:
                                    st.error("Failed to send email.")
            
            st.markdown("---")
            
            # Action Buttons
            col_btn1, col_btn2 = st.columns(2)
            
            # Save Delivery Button
            with col_btn1:
                if st.button("💾 Save Delivery", type="primary", use_container_width=True, key="save_delivery_btn"):
                    if not supplier or not product or ordered_qty == 0 or received_qty == 0:
                        st.error("❌ Please fill all required fields")
                    else:
                        try:
                            with st.spinner("Saving to Supabase..."):
                                success, error = save_delivery_to_supabase(
                                    supplier_id=supplier_id,
                                    product_code=product_code,
                                    ordered_qty=ordered_qty,
                                    received_qty=received_qty,
                                    delivery_date=delivery_date
                                )
                                
                                if success:
                                    st.success("✅ Delivery recorded successfully!")
                                    
                                    # Mark PO as delivered if selected
                                    if is_po_selected:
                                        mark_po_delivered(st.session_state.selected_po_data['po_id'])
                                        st.success(f"✅ PO marked as DELIVERED")
                                    
                                    # Send email alert
                                    disc_qty = received_qty - ordered_qty
                                    if disc_qty != 0:
                                        send_delivery_alert(
                                            supplier_name=supplier,
                                            product_name=product,
                                            ordered_qty=ordered_qty,
                                            received_qty=received_qty,
                                            discrepancy_qty=disc_qty,
                                            delivery_date=delivery_date.strftime('%Y-%m-%d'),
                                            po_id=st.session_state.selected_po_data['po_id'] if is_po_selected else 'N/A'
                                        )
                                    
                                    # Clear PO selection
                                    st.session_state.selected_po_data = None
                                    
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to save: {error}")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            # Save Draft Button
            with col_btn2:
                if st.button("📝 Save Draft", use_container_width=True, key="save_draft_btn"):
                    if not supplier or not product or ordered_qty == 0 or received_qty == 0:
                        st.error("❌ Please fill all required fields")
                    else:
                        try:
                            with st.spinner("Saving draft..."):
                                success = save_draft_to_supabase(
                                    supplier_name=supplier,
                                    product_name=product,
                                    ordered_qty=ordered_qty,
                                    received_qty=received_qty,
                                    delivery_date=delivery_date.strftime('%Y-%m-%d')
                                )
                                if success:
                                    st.success("✅ Draft saved!")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            # Display Drafts
            st.markdown("---")
            st.markdown("#### 🗂️ Saved Delivery Drafts")
            
            drafts_df = get_delivery_drafts()
            if drafts_df.empty:
                st.info("No saved drafts yet.")
            else:
                display_columns = ['draft_id', 'created_at', 'order_number', 'supplier_name', 'product_name', 
                                  'ordered_quantity', 'received_quantity', 'discrepancy_quantity', 'delivery_date']
                existing_columns = [col for col in display_columns if col in drafts_df.columns]
                st.dataframe(drafts_df[existing_columns], use_container_width=True, hide_index=True)

    # =========================================================
    # TAB 3: DISCREPANCY TREND ANALYZER
    # =========================================================
    with tab3:
        st.markdown('<div class="section-title">🏭 Supplier Breakdown</div>', unsafe_allow_html=True)

        # Date range selector for trend analyzer
        col1, col2 = st.columns(2)
        with col1:
            trend_start = st.date_input("📅 From Date", value=date.today() - timedelta(days=90), key="trend_start_date")
        with col2:
            trend_end = st.date_input("📅 To Date", value=date.today(), key="trend_end_date")

        trend_df = get_deliveries_for_reconciliation(trend_start, trend_end)

        if len(trend_df) >= 5:
            # Supplier Performance
            supplier_trend = trend_df.groupby("supplier").agg(
                Shortage_Rate=("status", lambda x: (x == "Short").mean() * 100),
                Deliveries=("ordered", "count"),
            ).reset_index().sort_values("Shortage_Rate", ascending=False)

            for _, row in supplier_trend.iterrows():
                rate = row["Shortage_Rate"]
                color = "🔴" if rate > 30 else "🟡" if rate > 15 else "🟢"
                status = "High Risk" if rate > 30 else "Medium Risk" if rate > 15 else "Low Risk"
                st.write(f"{color} **{row['supplier']}** — {rate:.0f}% shortage rate ({status}) | 📦 {row['Deliveries']:.0f} deliveries")

            st.markdown("---")

            # Most Problematic Product
            problem_products = trend_df[trend_df["status"] == "Short"].groupby("product").size().sort_values(ascending=False)
            if not problem_products.empty:
                top_product = problem_products.index[0]
                top_count = problem_products.values[0]
                st.write(f"📦 **Most Problematic Product:** {top_product} ({top_count} shortage{'s' if top_count > 1 else ''})")
                st.caption("⚠️ This product has the highest number of shortages")
            else:
                st.success("✅ No problematic products detected")

            st.markdown("---")

            # Financial Impact
            total_loss = abs(trend_df[trend_df["financial_impact"] < 0]["financial_impact"].sum())
            st.write(f"💰 **Total Financial Loss:** LKR {total_loss:,.0f}")
            if total_loss > 0:
                st.caption("💡 Fixing high-risk suppliers can recover this amount")
            else:
                st.caption("✅ No financial loss from shortages")

            st.markdown("---")

            # Recommendations
            high_risk = supplier_trend[supplier_trend["Shortage_Rate"] > 30]
            medium_risk = supplier_trend[(supplier_trend["Shortage_Rate"] > 15) & (supplier_trend["Shortage_Rate"] <= 30)]

            if not high_risk.empty:
                names = ", ".join(high_risk["supplier"].tolist())
                st.warning(f"🎯 **Immediate Action Required:** {len(high_risk)} high-risk supplier(s) — {names}")
                st.caption("✅ Recommendation: Review contracts or add 25% safety stock")
            elif not medium_risk.empty:
                st.info(f"📋 **Monitor Closely:** {len(medium_risk)} supplier(s) need attention")
                st.caption("✅ Recommendation: Track next 3 deliveries before deciding")
            else:
                st.success("✅ **All Good!** No high-risk suppliers detected")
                st.caption("✅ Recommendation: Continue current monitoring process")

        else:
            needed = max(0, 5 - len(trend_df))
            st.info(f"📊 Need {needed} more deliveries for analysis (currently have {len(trend_df)} deliveries)")
            st.progress(min(len(trend_df) / 5, 1.0))
            st.caption("Add more deliveries through the 'Record Delivery' tab to enable detailed analysis")

    st.markdown