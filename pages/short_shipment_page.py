# pages/short_shipment_page.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import numpy as np
import sqlite3
import sys
import os
import smtplib
import plotly.graph_objects as go
from email.mime.text import MIMEText

# =========================================================
# HELPER FUNCTIONS (OUTSIDE render_short_shipment)
# =========================================================
def init_delivery_draft_table():
    db_conn = sqlite3.connect('supermarket.db')
    cursor = db_conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS delivery_drafts (
            draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            order_number TEXT,
            supplier_name TEXT,
            product_name TEXT,
            ordered_quantity REAL,
            received_quantity REAL,
            discrepancy_quantity REAL,
            discrepancy_percentage REAL,
            delivery_date TEXT,
            source_type TEXT
        )
    ''')
    db_conn.commit()
    db_conn.close()

def get_delivery_drafts(limit=50):
    db_conn = sqlite3.connect('supermarket.db')
    query = """
        SELECT draft_id, created_at, order_number, supplier_name, product_name,
               ordered_quantity, received_quantity, discrepancy_quantity,
               discrepancy_percentage, delivery_date, source_type
        FROM delivery_drafts ORDER BY draft_id DESC LIMIT ?
    """
    drafts_df = pd.read_sql_query(query, db_conn, params=[limit])
    db_conn.close()
    return drafts_df

def save_delivery_draft(order_number, supplier_name, product_name, ordered_qty, received_qty, delivery_date, source_type):
    disc_qty = float(received_qty) - float(ordered_qty)
    disc_pct = (disc_qty / float(ordered_qty) * 100) if float(ordered_qty) > 0 else 0.0

    db_conn = sqlite3.connect('supermarket.db')
    cursor = db_conn.cursor()
    cursor.execute(
        """
        INSERT INTO delivery_drafts (
            order_number, supplier_name, product_name,
            ordered_quantity, received_quantity,
            discrepancy_quantity, discrepancy_percentage,
            delivery_date, source_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(order_number),
            str(supplier_name),
            str(product_name),
            float(ordered_qty),
            float(received_qty),
            float(disc_qty),
            float(round(disc_pct, 1)),
            str(delivery_date),
            str(source_type),
        ),
    )
    db_conn.commit()
    db_conn.close()

def get_pending_purchase_orders():
    try:
        from modules.short_shipment_detector.database import get_db_connection
        conn = get_db_connection()
        
        po_response = conn.table("purchase_orders")\
            .select("po_id, replenishment_order_id, supplier_id, status")\
            .neq("status", "DELIVERED")\
            .execute()
        
        if not po_response.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(po_response.data)
        df = df.drop_duplicates(subset=['po_id'])
        
        suppliers_response = conn.table("suppliers").select("supplier_id, supplier_name, email").execute()
        if suppliers_response.data:
            suppliers_df = pd.DataFrame(suppliers_response.data)
            df = df.merge(suppliers_df, left_on='supplier_id', right_on='supplier_id', how='left')
            df['supplier_name'] = df['supplier_name'].fillna('Unknown')
            df['supplier_email'] = df.get('email', '')
        
        rep_ids = df['replenishment_order_id'].dropna().tolist()
        
        if rep_ids:
            rep_response = conn.table("replenishment_orders")\
                .select("order_id, product_code, suggested_qty")\
                .in_("order_id", rep_ids)\
                .execute()
            
            if rep_response.data:
                rep_df = pd.DataFrame(rep_response.data)
                rep_df.rename(columns={'order_id': 'replenishment_order_id', 'suggested_qty': 'ordered_qty'}, inplace=True)
                df = df.merge(rep_df, on='replenishment_order_id', how='left')
                
                product_codes = df['product_code'].dropna().unique().tolist()
                if product_codes:
                    prod_response = conn.table("product_catalog")\
                        .select("product_code, product_name")\
                        .in_("product_code", product_codes)\
                        .execute()
                    
                    if prod_response.data:
                        prod_df = pd.DataFrame(prod_response.data)
                        df = df.merge(prod_df, on='product_code', how='left')
                        df['product_name'] = df['product_name'].fillna('Unknown')
                    else:
                        df['product_name'] = 'Unknown'
                else:
                    df['product_name'] = 'Unknown'
            else:
                df['product_name'] = 'Unknown'
                df['ordered_qty'] = 0
        else:
            df['product_name'] = 'Unknown'
            df['ordered_qty'] = 0
        
        df['ordered_qty'] = df['ordered_qty'].fillna(0).astype(int)
        return df
        
    except Exception as e:
        st.error(f"Error fetching POs: {e}")
        return pd.DataFrame()

def validate_dates(start_date, end_date):
    errors = []
    if start_date > end_date:
        errors.append("Start date cannot be after end date")
    if (end_date - start_date).days > 365:
        errors.append("Date range exceeds 365 days")
    today = date.today()
    if start_date > today:
        errors.append("Start date cannot be in the future")
    if end_date > today:
        errors.append("End date cannot be in the future")
    if (end_date - start_date).days < 1:
        errors.append("Date range must be at least 1 day")
    return len(errors) == 0, errors

def ensure_sample_data():
    return True

def send_delivery_alert(supplier_name, product_name, ordered_qty, received_qty, discrepancy_qty, delivery_date, po_id=None):
    your_email = "hashiniwickramathilaka@gmail.com"
    
    if discrepancy_qty < 0:
        alert_type = "⚠️ SHORT SHIPPED"
        alert_icon = "⚠️"
        message = f"CRITICAL: Shipment was short by {abs(discrepancy_qty):,.0f} units!"
        action_needed = "Contact supplier immediately for credit note"
    elif discrepancy_qty > 0:
        alert_type = "📦 OVER DELIVERED"
        alert_icon = "📦"
        message = f"Note: Shipment had {discrepancy_qty:,.0f} extra units!"
        action_needed = "Review if extra units are needed or return to supplier"
    else:
        alert_type = "✅ ACCURATE DELIVERY"
        alert_icon = "✅"
        message = "Perfect! Shipment matched ordered quantity exactly."
        action_needed = "No action required - update inventory"
    
    pct = (abs(discrepancy_qty) / ordered_qty * 100) if ordered_qty > 0 else 0
    
    subject = f"{alert_icon} {alert_type}: {supplier_name} - {product_name}"
    
    body = f"""
         SUNRISE SUPERMARKET - DELIVERY STATUS REPORT       

{alert_icon} ALERT TYPE: {alert_type} {alert_icon}
Status:         {message}
Date & Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Delivery Date:  {delivery_date}
PO Reference:   {po_id if po_id else 'Manual Entry'}

🏢 SUPPLIER INFORMATION

Supplier Name:  {supplier_name}
Alert Sent To:  {your_email} (Project Demo Mode)

📦 DELIVERY DETAILS

Product:        {product_name}
Ordered Qty:    {ordered_qty:,.0f} units
Received Qty:   {received_qty:,.0f} units
Variance:       {discrepancy_qty:+,.0f} units
Variance Pct:   {pct:+.1f}%

"""
    
    if discrepancy_qty < 0:
        body += f"""
⚠️ SHORTAGE DETAILS

Shortage Qty:   {abs(discrepancy_qty):,.0f} units
Shortage Pct:   {pct:.1f}%

📌 RECOMMENDED ACTION

{action_needed}
• Request credit note for missing {abs(discrepancy_qty):,.0f} units
• Adjust next purchase order to compensate
"""
    elif discrepancy_qty > 0:
        body += f"""
📦 OVERAGE DETAILS

Overage Qty:    {discrepancy_qty:,.0f} units
Overage Pct:    {pct:.1f}%

📌 RECOMMENDED ACTION

{action_needed}
• Check if extra units can be stored
• Negotiate return or discount for overage
"""
    else:
        body += f"""
✅ ACCURACY DETAILS

This is a perfect delivery! No discrepancies found.

📌 RECOMMENDED ACTION

{action_needed}
• Update inventory system
• Mark supplier as reliable for this product
"""
    
    body += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated alert from the SUNRISE Supermarket
Short-Shipment Detection System - Project Demonstration Mode
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    sender_email = "hashiniwickramathilaka@gmail.com"
    sender_password = "egjososgumoiiqqs"
    
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = your_email
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

from modules.short_shipment_detector.detectors import ShortShipmentDetector
from modules.short_shipment_detector.utils import (
    validate_email,
    validate_phone,
    validate_supplier_id,
    validate_product_code,
)

# =========================================================
# MAIN RENDER FUNCTION
# =========================================================
def render_short_shipment():
    
    from modules.short_shipment_detector.database import (
        get_db_connection, init_database,
        get_suppliers_sqlite, get_products_sqlite
    )
    
    init_database()
    init_delivery_draft_table()
    detector = ShortShipmentDetector()
    
    conn = get_db_connection()
    conn_type = "supabase" if hasattr(conn, 'table') else "sqlite"
    
    # CSS Styling
    st.markdown("""
        <style>
        .main-title {
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin-bottom: 0.5rem;
        }
        .subtitle {
            text-align: center;
            color: #6c757d;
            margin-bottom: 1.5rem;
        }
        .section-header {
            font-size: 1.3rem;
            font-weight: 600;
            color: #2c3e50;
            border-left: 4px solid #667eea;
            padding-left: 12px;
            margin: 20px 0 15px 0;
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
            border-radius: 10px;
            padding: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .footer {
            text-align: center;
            padding: 15px;
            margin-top: 20px;
            color: #6c757d;
            font-size: 0.75rem;
            border-top: 1px solid #dee2e6;
        }
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        </style>
    """, unsafe_allow_html=True)
    
   
    def get_products_from_catalog():
        try:
            if conn_type == "supabase":
                response = conn.table("product_catalog").select("*").order("product_name").execute()
                return pd.DataFrame(response.data)
            else:
                db_conn = sqlite3.connect('supermarket.db')
                df = pd.read_sql_query("SELECT * FROM product_catalog ORDER BY product_name", db_conn)
                db_conn.close()
                return df
        except Exception as e:
            st.error(f"Error fetching products: {e}")
            return pd.DataFrame()
    
    def get_deliveries(start_date, end_date):
        try:
            if conn_type == "supabase":
                start_str = start_date.strftime('%Y-%m-%d')
                end_str = end_date.strftime('%Y-%m-%d')
                response = conn.table("deliveries")\
                    .select("""
                        delivery_id,
                        invoice_number,
                        delivery_date,
                        supplier_id,
                        suppliers(supplier_name),
                        delivery_items(
                            delivery_item_id,
                            product_code,
                            billed_quantity,
                            received_quantity,
                            product_catalog(product_name, category, unit_price)
                        )
                    """)\
                    .gte("delivery_date", start_str)\
                    .lte("delivery_date", end_str)\
                    .order("delivery_date", desc=True)\
                    .execute()
                data = []
                for delivery in response.data:
                    supplier_name = delivery.get('suppliers', {}).get('supplier_name', 'Unknown') if delivery.get('suppliers') else 'Unknown'
                    for item in delivery.get('delivery_items', []):
                        product_info = item.get('product_catalog', {})
                        billed = float(item.get('billed_quantity', 0))
                        received = float(item.get('received_quantity', 0))
                        disc = received - billed
                        disc_pct = (disc / billed * 100) if billed > 0 else 0
                        unit_price = float(product_info.get('unit_price', 0)) if product_info.get('unit_price') else 0
                        data.append({
                            'delivery_date': delivery.get('delivery_date'),
                            'invoice_number': delivery.get('invoice_number'),
                            'supplier_name': supplier_name,
                            'product_name': product_info.get('product_name', 'Unknown'),
                            'category': product_info.get('category', 'Unknown'),
                            'cost_price': unit_price,
                            'ordered_quantity': billed,
                            'received_quantity': received,
                            'discrepancy_quantity': disc,
                            'discrepancy_percentage': round(disc_pct, 1),
                            'financial_impact': disc * unit_price,
                        })
                df = pd.DataFrame(data)
                if not df.empty:
                    conditions = [
                        abs(df['discrepancy_quantity']) < 0.01,
                        df['discrepancy_quantity'] < 0,
                        df['discrepancy_quantity'] > 0
                    ]
                    choices = ['✅ Accurate', '⚠️ Short Shipped', '📦 Over Delivered']
                    df['status'] = np.select(conditions, choices, default='Unknown')
                return df
            else:
                return pd.DataFrame()
        except Exception as e:
            st.error(f"Error fetching deliveries: {e}")
            return pd.DataFrame()
    
    def get_delivery_data_for_reconciliation(start_date, end_date):
        try:
            if conn_type == "supabase":
                start_str = start_date.strftime('%Y-%m-%d')
                end_str = end_date.strftime('%Y-%m-%d')
                response = conn.table("deliveries")\
                    .select("""
                        delivery_id,
                        invoice_number,
                        delivery_date,
                        supplier_id,
                        suppliers(supplier_name, email),
                        delivery_items(
                            product_code,
                            billed_quantity,
                            received_quantity,
                            product_catalog(product_name, unit_price)
                        )
                    """)\
                    .gte("delivery_date", start_str)\
                    .lte("delivery_date", end_str)\
                    .order("delivery_date", desc=True)\
                    .execute()
                data = []
                for delivery in response.data:
                    supplier_info = delivery.get('suppliers', {})
                    supplier_name = supplier_info.get('supplier_name', 'Unknown')
                    supplier_email = supplier_info.get('email', '')
                    for item in delivery.get('delivery_items', []):
                        product_info = item.get('product_catalog', {})
                        billed = float(item.get('billed_quantity', 0))
                        received = float(item.get('received_quantity', 0))
                        disc_qty = received - billed
                        disc_pct = (disc_qty / billed * 100) if billed > 0 else 0
                        unit_price = float(product_info.get('unit_price', 0))
                        financial_impact = disc_qty * unit_price
                        data.append({
                            'date': delivery.get('delivery_date'),
                            'invoice': delivery.get('invoice_number'),
                            'supplier': supplier_name,
                            'supplier_email': supplier_email,
                            'product': product_info.get('product_name', 'Unknown'),
                            'product_code': item.get('product_code'),
                            'ordered': billed,
                            'received': received,
                            'discrepancy_qty': disc_qty,
                            'discrepancy_pct': disc_pct,
                            'unit_price': unit_price,
                            'financial_impact': financial_impact,
                            'status': 'Short' if disc_qty < 0 else 'Over' if disc_qty > 0 else 'Accurate',
                            'source': 'Finalized'
                        })
                return pd.DataFrame(data)
            else:
                return pd.DataFrame()
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return pd.DataFrame()
    
    def calculate_next_order_adjustment(supplier_data):
        if supplier_data.empty:
            return None
        product_summary = supplier_data.groupby(['supplier', 'product_code', 'product']).agg({
            'ordered': 'sum',
            'received': 'sum',
            'discrepancy_qty': 'sum',
            'financial_impact': 'sum',
            'unit_price': 'first'
        }).reset_index()
        adjustments = []
        for _, row in product_summary.iterrows():
            cumulative_shortage = abs(row['discrepancy_qty']) if row['discrepancy_qty'] < 0 else 0
            cumulative_overage = row['discrepancy_qty'] if row['discrepancy_qty'] > 0 else 0
            if cumulative_shortage > 0:
                adjustment = {
                    'supplier': row['supplier'],
                    'product': row['product'],
                    'product_code': row['product_code'],
                    'cumulative_shortage': cumulative_shortage,
                    'cumulative_overage': cumulative_overage,
                    'net_position': -cumulative_shortage + cumulative_overage,
                    'adjustment_type': 'Add to Next Order',
                    'adjustment_qty': cumulative_shortage,
                    'financial_impact': row['financial_impact'],
                    'reason': f"Short by {cumulative_shortage:,.0f} units across deliveries",
                    'action': f"📦 Add {cumulative_shortage:,.0f} extra units to next order"
                }
            elif cumulative_overage > 0:
                adjustment = {
                    'supplier': row['supplier'],
                    'product': row['product'],
                    'product_code': row['product_code'],
                    'cumulative_shortage': 0,
                    'cumulative_overage': cumulative_overage,
                    'net_position': cumulative_overage,
                    'adjustment_type': 'Credit for Next Order',
                    'adjustment_qty': cumulative_overage,
                    'financial_impact': row['financial_impact'],
                    'reason': f"Over by {cumulative_overage:,.0f} units across deliveries",
                    'action': f"💰 Credit {cumulative_overage:,.0f} units for next order"
                }
            else:
                adjustment = {
                    'supplier': row['supplier'],
                    'product': row['product'],
                    'product_code': row['product_code'],
                    'cumulative_shortage': 0,
                    'cumulative_overage': 0,
                    'net_position': 0,
                    'adjustment_type': 'No Adjustment',
                    'adjustment_qty': 0,
                    'financial_impact': 0,
                    'reason': "All deliveries accurate",
                    'action': "✅ No adjustment needed"
                }
            adjustments.append(adjustment)
        return pd.DataFrame(adjustments)
    
    ensure_sample_data()
    
    # Navigation Tabs
    tab1, tab2,tab3 = st.tabs(["📊 Dashboard", "📦 Record Delivery","📈  Discrepancy Trend Analyzer" ])   
     # =========================================================
    # TAB 1: DASHBOARD & ORDER RECONCILIATION
    # =========================================================
    with tab1:
        st.markdown('<div class="section-header">📊 Dashboard & Order Reconciliation</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            rec_start = st.date_input("📅 From Date", value=date.today() - timedelta(days=90), key="recon_start_date")
        with col2:
            rec_end = st.date_input("📅 To Date", value=date.today(), key="recon_end_date")
        
        rec_df = get_delivery_data_for_reconciliation(rec_start, rec_end)
        
        if rec_df.empty:
            st.info("📭 No delivery data found for the selected period.")
        else:
            total_orders = rec_df['ordered'].sum()
            total_received = rec_df['received'].sum()
            total_shortage = rec_df[rec_df['discrepancy_qty'] < 0]['discrepancy_qty'].sum()
            total_financial_impact = rec_df['financial_impact'].sum()
            
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
            status_counts = rec_df['status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            status_map = {'Short': '⚠️ Short Shipped', 'Over': '📦 Over Delivered', 'Accurate': '✅ Accurate'}
            status_counts['Display Status'] = status_counts['Status'].map(status_map)
            fig = px.pie(status_counts, values='Count', names='Display Status', title='Delivery Status Distribution', hole=0.4, color_discrete_sequence=['#e74c3c','#f39c12','#2ecc71'])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            show_only = st.selectbox("🔍 Filter Adjustments", ["All Adjustments", "Only Shortages", "Only Credits", "No Adjustment Needed"], key="rec_show_filter")
            adjustments_df = calculate_next_order_adjustment(rec_df)
            
            if adjustments_df.empty:
                    st.info(f"📭 No {show_only.lower()} found")
            else:
                    st.markdown("### 📋 Recommended Adjustments for Next Order")
                    
                    # Create product summary from rec_df (original data)
                    product_summary = rec_df.groupby(['supplier', 'product']).agg({
                        'ordered': 'sum', 
                        'received': 'sum', 
                        'discrepancy_qty': 'sum', 
                        'financial_impact': 'sum'
                    }).reset_index()
                    
                    # Merge adjustments with product summary
                    enhanced_df = adjustments_df.merge(
                        product_summary[['supplier', 'product', 'ordered', 'received', 'discrepancy_qty']], 
                        on=['supplier', 'product'], 
                        how='left'
                    )
                    
                    # Create display dataframe
                    display_df = enhanced_df[[
                        'supplier', 'product', 'ordered', 'received', 
                        'discrepancy_qty', 'adjustment_type', 'adjustment_qty', 'reason'
                    ]].copy()
                    
                    display_df.columns = [
                        'Supplier', 'Product', 'Ordered Qty', 'Received Qty', 
                        'Variance', 'Adjustment Type', 'Adjustment Qty', 'Reason'
                    ]
                    
                    # Format numbers
                    display_df['Ordered Qty'] = display_df['Ordered Qty'].apply(lambda x: f"{x:,.0f}")
                    display_df['Received Qty'] = display_df['Received Qty'].apply(lambda x: f"{x:,.0f}")
                    display_df['Variance'] = display_df['Variance'].apply(lambda x: f"{x:+,.0f}")
                    display_df['Adjustment Qty'] = display_df['Adjustment Qty'].apply(lambda x: f"{x:,.0f}")
                    
                    # Display the dataframe
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                                        # Download button
                    csv_data = enhanced_df[[
                        'supplier', 'product', 'ordered', 'received', 
                        'discrepancy_qty', 'adjustment_type', 'adjustment_qty', 'reason'
                    ]].to_csv(index=False)
                    
                    st.download_button(
                        label="📥 Download Adjustments as CSV", 
                        data=csv_data, 
                        file_name=f"adjustments_{date.today()}.csv", 
                        mime="text/csv", 
                        key="download_adjustments"
                    )
              
    # =========================================================
    # TAB 2: RECORD DELIVERY WITH AUTO-FILL & EMAIL ALERTS
    # =========================================================
    with tab2:
        st.markdown('<div class="section-header">📦 Record New Delivery</div>', unsafe_allow_html=True)

        if conn_type == "supabase":
            suppliers_df = pd.DataFrame(conn.table("suppliers").select("supplier_id, supplier_name, email").execute().data)
            products_df = get_products_from_catalog()
        else:
            suppliers_df = get_suppliers_sqlite()
            products_df = get_products_sqlite()

        if suppliers_df.empty or products_df.empty:
            st.warning("⚠️ Please add suppliers and products first.")
        else:
            st.success(f"✅ Found {len(suppliers_df)} suppliers and {len(products_df)} products")
            
            pending_pos = get_pending_purchase_orders()
            
            if not pending_pos.empty and 'po_id' in pending_pos.columns:
                st.info(f"📋 {len(pending_pos)} pending purchase orders from Replenishment System")
                
                pending_pos['display'] = pending_pos.apply(
                    lambda row: f"📄 {str(row['po_id'])[:8]}... | 🏢 {row.get('supplier_name', 'Unknown')} | 📦 {row.get('product_name', 'Unknown')} | 🔢 Qty: {row.get('ordered_qty', 0)}",
                    axis=1
                )
                pending_pos = pending_pos.drop_duplicates(subset=['po_id'])
                selected_label = st.selectbox(
                    "🔽 Select Purchase Order (Auto-fill from Replenishment)", 
                    [""] + pending_pos['display'].tolist(),
                    key="po_selectbox"
                )
                
                if selected_label:
                    po_data = pending_pos[pending_pos['display'] == selected_label].iloc[0]
                    st.session_state['auto_supplier'] = po_data.get('supplier_name', '')
                    st.session_state['auto_product'] = po_data.get('product_name', '')
                    st.session_state['auto_ordered_qty'] = int(po_data.get('ordered_qty', 0))
                    st.session_state['selected_po_id'] = po_data.get('po_id')
                    st.session_state['auto_supplier_email'] = po_data.get('supplier_email', '')
                    
                    st.success(f"""
                    ✅ **PO Selected - Fields Auto-Filled:**
                    - Supplier: {po_data.get('supplier_name', 'Unknown')}
                    - Product: {po_data.get('product_name', 'Unknown')}
                    - Ordered Quantity: {int(po_data.get('ordered_qty', 0))} units
                    """)
                    
                    st.info("📝 **Only enter the Received Quantity below. Other fields are pre-filled from the PO.**")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🏢 Delivery Information")
                supplier_list = suppliers_df['supplier_name'].tolist()
                auto_supplier = st.session_state.get('auto_supplier', '')
                
                if auto_supplier and auto_supplier in supplier_list:
                    supplier_index = supplier_list.index(auto_supplier)
                    supplier = st.selectbox("Supplier *", supplier_list, index=supplier_index, key="supplier_selectbox")
                else:
                    supplier = st.selectbox("Supplier *", supplier_list, key="supplier_normal")
                
                if supplier:
                    supplier_data = suppliers_df[suppliers_df['supplier_name'] == supplier].iloc[0]
                    supplier_id = supplier_data['supplier_id']
                    supplier_email = supplier_data.get('email', '')
                else:
                    supplier_id = None
                    supplier_email = ''
                
                delivery_date = st.date_input("Delivery Date", value=date.today(), key="delivery_date_input")
            
            with col2:
                st.markdown("#### 📦 Product Information")
                product_list = products_df['product_name'].tolist()
                auto_product = st.session_state.get('auto_product', '')
                
                if auto_product and auto_product in product_list:
                    product_index = product_list.index(auto_product)
                    product = st.selectbox("Product *", product_list, index=product_index, key="product_selectbox")
                else:
                    product = st.selectbox("Product *", product_list, key="product_normal")
                
                auto_qty = st.session_state.get('auto_ordered_qty', 0)
                ordered_qty_key = f"ordered_qty_{st.session_state.get('selected_po_id', 'none')}"
                
                ordered_qty = st.number_input(
                    "Ordered Quantity", 
                    min_value=0, 
                    value=auto_qty, 
                    step=10, 
                    key=ordered_qty_key
                )
                
                received_qty = st.number_input(
                    "Received Quantity *", 
                    min_value=0, 
                    value=0, 
                    step=10, 
                    key="received_qty_input"
                )
            
            disc_qty = 0
            disc_pct = 0
            
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
                
                if disc_qty != 0:
                    st.markdown("---")
                    st.markdown("#### 📧 Send Alert")
                    
                    col_email1, col_email2 = st.columns([3, 1])
                    with col_email1:
                        if disc_qty < 0:
                            st.warning(f"⚠️ Shortage detected: {abs(disc_qty)} units missing")
                        elif disc_qty > 0:
                            st.info(f"📦 Over delivery detected: {disc_qty} extra units")
                    
                    with col_email2:
                        if st.button("📧 Send Email Alert", key="send_email_visible_btn", use_container_width=True):
                            with st.spinner("Sending email..."):
                                email_sent = send_delivery_alert(
                                    supplier_name=supplier,
                                    product_name=product,
                                    ordered_qty=ordered_qty,
                                    received_qty=received_qty,
                                    discrepancy_qty=disc_qty,
                                    delivery_date=delivery_date.strftime('%Y-%m-%d'),
                                    po_id=st.session_state.get('selected_po_id', 'N/A')
                                )
                                if email_sent:
                                    st.success(f"📧 Alert sent to your email!")
                                else:
                                    st.error("Failed to send email.")
            else:
                st.info("📊 Enter ordered and received quantities to see discrepancy summary")
            
            st.markdown("---")
            col_btn1, col_btn2 = st.columns(2)
            
            if col_btn1.button("💾 Save Delivery", type="primary", use_container_width=True, key="save_delivery_btn"):
                if not supplier or not product or ordered_qty == 0 or received_qty == 0:
                    st.error("❌ Please fill all required fields")
                else:
                    try:
                        selected_product = products_df[products_df['product_name'] == product].iloc[0]
                        product_code = selected_product['product_code']
                        unit_price = selected_product.get('unit_price', 0)
                        disc_qty = received_qty - ordered_qty
                        
                        if conn_type == "supabase":
                            delivery_result = conn.table("deliveries").insert({
                                "supplier_id": supplier_id,
                                "invoice_number": f"DEL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                                "delivery_date": delivery_date.isoformat()
                            }).execute()
                            
                            if delivery_result.data:
                                delivery_id = delivery_result.data[0]['delivery_id']
                                conn.table("delivery_items").insert({
                                    "delivery_id": delivery_id,
                                    "product_code": product_code,
                                    "billed_quantity": ordered_qty,
                                    "received_quantity": received_qty
                                }).execute()
                                
                                selected_po_id = st.session_state.get('selected_po_id')
                                if selected_po_id:
                                    try:
                                        conn.table("purchase_orders").update({"status": "DELIVERED"}).eq("po_id", selected_po_id).execute()
                                        conn.table("replenishment_orders").update({"status": "DELIVERED"}).eq("order_id", selected_po_id).execute()
                                        st.success(f"✅ PO {selected_po_id[:8]} removed from dropdown")
                                    except Exception:
                                        pass
                            
                            st.info(f"📧 Sending delivery report...")
                            email_sent = send_delivery_alert(
                                supplier_name=supplier,
                                product_name=product,
                                ordered_qty=ordered_qty,
                                received_qty=received_qty,
                                discrepancy_qty=disc_qty,
                                delivery_date=delivery_date.strftime('%Y-%m-%d'),
                                po_id=st.session_state.get('selected_po_id', 'N/A')
                            )
                            if email_sent:
                                st.success(f"📧 Alert sent!")
                            
                            st.success("✅ Delivery recorded successfully!")
                            st.balloons()
                            
                            for key in ['auto_supplier', 'auto_product', 'auto_ordered_qty', 'selected_po_id', 'auto_supplier_email']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error saving delivery: {e}")
            
            if col_btn2.button("📝 Save Draft", use_container_width=True, key="save_draft_btn"):
                if not supplier or not product or ordered_qty == 0 or received_qty == 0:
                    st.error("❌ Please fill all required fields")
                else:
                    order_num = f"DRAFT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    try:
                        save_delivery_draft(order_num, supplier, product, ordered_qty, received_qty, delivery_date.strftime('%Y-%m-%d'), "manual")
                        st.success("✅ Draft saved!")
                        for key in ['auto_supplier', 'auto_product', 'auto_ordered_qty', 'selected_po_id', 'auto_supplier_email']:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving draft: {e}")
        
        st.markdown("---")
        st.markdown("#### 🗂️ Saved Delivery Drafts")
        drafts_df = get_delivery_drafts(limit=50)
        if drafts_df.empty:
            st.info("No saved drafts yet.")
        else:
            view_df = drafts_df.copy()
            view_df.columns = ["Draft ID", "Saved At", "Order/Invoice", "Supplier", "Product", "Ordered Qty", "Received Qty", "Variance Qty", "Variance %", "Delivery Date", "Source"]
            st.dataframe(view_df, use_container_width=True, hide_index=True)

           # =========================================================
    # TAB 3: SUPPLIER BREAKDOWN
    # =========================================================
    with tab3:
        st.markdown("### 🏭 Supplier Breakdown")
        
        if len(rec_df) >= 5:
            
            # Calculate supplier performance
            supplier_trend = rec_df.groupby('supplier').agg(
                Shortage_Rate=('status', lambda x: (x == 'Short').mean() * 100),
                Deliveries=('ordered', 'count')
            ).reset_index()
            supplier_trend = supplier_trend.sort_values('Shortage_Rate', ascending=False)
            
            # Display in one line per supplier
            for _, row in supplier_trend.iterrows():
                rate = row['Shortage_Rate']
                if rate > 30:
                    color = "🔴"
                    status = "High Risk"
                elif rate > 15:
                    color = "🟡"
                    status = "Medium Risk"
                else:
                    color = "🟢"
                    status = "Low Risk"
                
                st.write(f"{color} **{row['supplier']}** - {rate:.0f}% shortage rate ({status}) | 📦 {row['Deliveries']:.0f} deliveries")
            
            st.markdown("---")
            
            # =========================================================
            # TOP PROBLEM PRODUCT
            # =========================================================
            problem_products = rec_df[rec_df['status'] == 'Short'].groupby('product').size().sort_values(ascending=False)
            if not problem_products.empty:
                top_product = problem_products.index[0]
                top_count = problem_products.values[0]
                st.write(f"📦 **Most Problematic Product:** {top_product} ({top_count} shortage{'s' if top_count > 1 else ''})")
                st.caption("⚠️ This product has the highest number of shortages")
            else:
                st.success("✅ No problematic products detected")
            
            st.markdown("---")
            
            # =========================================================
            # SAVINGS OPPORTUNITY
            # =========================================================
            total_loss = abs(rec_df[rec_df['financial_impact'] < 0]['financial_impact'].sum())
            if total_loss > 0:
                st.write(f"💰 **Total Financial Loss:** LKR {total_loss:,.0f}")
                st.caption("💡 Fixing high-risk suppliers can recover this amount")
            else:
                st.write("💰 **Total Financial Loss:** LKR 0")
                st.caption("✅ No financial loss from shortages")
            
            st.markdown("---")
            
            # =========================================================
            # RECOMMENDATION
            # =========================================================
            high_risk_count = len(supplier_trend[supplier_trend['Shortage_Rate'] > 30])
            medium_risk_count = len(supplier_trend[(supplier_trend['Shortage_Rate'] > 15) & (supplier_trend['Shortage_Rate'] <= 30)])
            
            if high_risk_count > 0:
                high_risk_names = supplier_trend[supplier_trend['Shortage_Rate'] > 30]['supplier'].tolist()
                st.warning(f"🎯 **Immediate Action Required:** {high_risk_count} high-risk supplier(s) - {', '.join(high_risk_names)}")
                st.caption("✅ Recommendation: Review contracts or add 25% safety stock")
            elif medium_risk_count > 0:
                st.info(f"📋 **Monitor Closely:** {medium_risk_count} supplier(s) need attention")
                st.caption("✅ Recommendation: Track next 3 deliveries before deciding")
            else:
                st.success("✅ **All Good!** No high-risk suppliers detected")
                st.caption("✅ Recommendation: Continue current monitoring process")
        
        else:
            needed = 5 - len(rec_df)
            st.info(f"📊 Need {needed} more deliveries for analysis")
            st.progress(min(len(rec_df) / 5, 1.0))
    
    # Footer
    st.markdown("---")
    st.markdown('<div class="footer">Sunrise Supermarket SLIIT</div>', unsafe_allow_html=True)a