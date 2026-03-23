# pages/short_shipment_page.py
import streamlit as st
import sys
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import numpy as np
import matplotlib.pyplot as plt
import sqlite3
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# =========================================================
# DATE VALIDATION FUNCTION
# =========================================================
def validate_dates(start_date, end_date):
    errors = []
    if start_date > end_date:
        errors.append("❌ Start date cannot be after end date")
    if (end_date - start_date).days > 365:
        errors.append("⚠️ Date range exceeds 365 days")
    today = date.today()
    if start_date > today:
        errors.append("⚠️ Start date cannot be in the future")
    if end_date > today:
        errors.append("⚠️ End date cannot be in the future")
    if (end_date - start_date).days < 1:
        errors.append("⚠️ Date range must be at least 1 day")
    return len(errors) == 0, errors




# Add module path
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'modules', 'short_shipment_detector'
))

from detectors import ShortShipmentDetector
from utils import validate_email, validate_phone, validate_supplier_id, validate_product_code


def render_short_shipment():
    """Wrapper that renders short shipment module inside shared app"""

    from database import (
        get_db_connection, init_database,
        add_sample_data, get_suppliers_sqlite, get_products_sqlite
    )

    init_database()
    detector = ShortShipmentDetector()

    def is_supabase(conn):
        return hasattr(conn, 'table') and callable(getattr(conn, 'table'))

    def is_sqlite(conn):
        return hasattr(conn, 'cursor') and hasattr(conn, 'execute')

    conn = get_db_connection()
    conn_type = "supabase" if is_supabase(conn) else "sqlite" if is_sqlite(conn) else "unknown"

    # =========================================================
    # Function to get products from product_catalog
    # =========================================================
    def get_products_from_catalog():
        """Fetch products from client's product_catalog table"""
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

    # =========================================================
    # Function to get deliveries
    # =========================================================
    def get_deliveries(start_date, end_date):
        try:
            if conn_type == "supabase":
                start_str = start_date.strftime('%Y-%m-%d')
                end_str = end_date.strftime('%Y-%m-%d')
                
                # Get deliveries with items and product info
                response = conn.table("deliveries")\
                    .select("""
                        delivery_id,
                        invoice_number,
                        delivery_date,
                        supplier_id,
                        suppliers(
                            supplier_name
                        ),
                        delivery_items(
                            delivery_item_id,
                            product_code,
                            billed_quantity,
                            received_quantity,
                            product_catalog(
                                product_name,
                                category,
                                unit_price
                            )
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
                
                # Add status
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
                # SQLite version
                query = """
                    SELECT d.delivery_date, d.order_number as invoice_number,
                           d.product_code, p.product_name, p.category,
                           p.unit_price as cost_price, d.ordered_quantity,
                           d.received_quantity, d.discrepancy_quantity,
                           d.discrepancy_percentage, d.financial_impact,
                           s.supplier_name
                    FROM deliveries d
                    LEFT JOIN product_catalog p ON d.product_code = p.product_code
                    LEFT JOIN suppliers s ON d.supplier_id = s.supplier_id
                    WHERE d.delivery_date BETWEEN ? AND ?
                    ORDER BY d.delivery_date DESC
                """
                db_conn = sqlite3.connect('supermarket.db')
                df = pd.read_sql_query(query, db_conn, params=[start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')])
                db_conn.close()
                
                if not df.empty:
                    conditions = [
                        abs(df['discrepancy_quantity']) < 0.01,
                        df['discrepancy_quantity'] < 0,
                        df['discrepancy_quantity'] > 0
                    ]
                    choices = ['✅ Accurate', '⚠️ Short Shipped', '📦 Over Delivered']
                    df['status'] = np.select(conditions, choices, default='Unknown')
                
                return df
        except Exception as e:
            st.error(f"Error fetching deliveries: {e}")
            return pd.DataFrame()

  
    # =========================================================
    # FUNCTION: Get delivery data for reconciliation
    # =========================================================
    def get_delivery_data_for_reconciliation(start_date, end_date):
        """Get all deliveries with discrepancy calculations for reconciliation tab"""
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
                    supplier_name = delivery.get('suppliers', {}).get('supplier_name', 'Unknown')
                    
                    for item in delivery.get('delivery_items', []):
                        product_info = item.get('product_catalog', {})
                        billed = float(item.get('billed_quantity', 0))
                        received = float(item.get('received_quantity', 0))
                        disc_qty = received - billed
                        disc_pct = (disc_qty / billed * 100) if billed > 0 else 0
                        unit_price = float(product_info.get('unit_price', 0))
                        financial_impact = disc_qty * unit_price
                        
                        data.append({
                            'delivery_id': delivery.get('delivery_id'),
                            'date': delivery.get('delivery_date'),
                            'invoice': delivery.get('invoice_number'),
                            'supplier': supplier_name,
                            'product': product_info.get('product_name', 'Unknown'),
                            'product_code': item.get('product_code'),
                            'ordered': billed,
                            'received': received,
                            'discrepancy_qty': disc_qty,
                            'discrepancy_pct': disc_pct,
                            'unit_price': unit_price,
                            'financial_impact': financial_impact,
                            'status': 'Short' if disc_qty < 0 else 'Over' if disc_qty > 0 else 'Accurate'
                        })
                
                return pd.DataFrame(data)
            else:
                # SQLite version
                query = """
                    SELECT 
                        d.delivery_id,
                        d.delivery_date as date,
                        d.order_number as invoice,
                        d.supplier_id,
                        s.supplier_name as supplier,
                        d.product_code,
                        p.product_name as product,
                        d.ordered_quantity as ordered,
                        d.received_quantity as received,
                        d.discrepancy_quantity as discrepancy_qty,
                        d.discrepancy_percentage as discrepancy_pct,
                        p.unit_price,
                        d.financial_impact
                    FROM deliveries d
                    LEFT JOIN suppliers s ON d.supplier_id = s.supplier_id
                    LEFT JOIN product_catalog p ON d.product_code = p.product_code
                    WHERE d.delivery_date BETWEEN ? AND ?
                    ORDER BY d.delivery_date DESC
                """
                db_conn = sqlite3.connect('supermarket.db')
                df = pd.read_sql_query(query, db_conn, params=[start_date, end_date])
                db_conn.close()
                
                if not df.empty:
                    df['status'] = df['discrepancy_qty'].apply(
                        lambda x: 'Short' if x < 0 else 'Over' if x > 0 else 'Accurate'
                    )
                
                return df
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return pd.DataFrame()
    # =========================================================
    # FUNCTION: Calculate compensation for next order
    # =========================================================
    def calculate_next_order_adjustment(supplier_data):
        """Calculate how to adjust next order to compensate"""
        
        if supplier_data.empty:
            return None
        
        # Group by product to calculate cumulative shortages
        product_summary = supplier_data.groupby(['product_code', 'product']).agg({
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
   
    # =========================================================
    # Navigation Tabs
    # =========================================================
    tab1, tab2, tab3 = st.tabs([
        "📊 Dashboard",
        "📦 Record Delivery",
        "🏆 Order Reconciliation"
    ])

    # =========================================================
    # TAB 1: DASHBOARD
    # =========================================================
    
    with tab1:
        st.markdown('<div class="section-title">📊 Shipment Dashboard</div>', unsafe_allow_html=True)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            start_date = st.date_input("From", value=date.today() - timedelta(days=30), key="dash_start")
        with col_d2:
            end_date = st.date_input("To", value=date.today(), key="dash_end")
        
        is_valid, errors = validate_dates(start_date, end_date)
        if not is_valid:
            for error in errors:
                st.warning(error)
            df = pd.DataFrame()
        else:
            df = get_deliveries(start_date, end_date)

        if df.empty:
            st.info("No deliveries found. Use 'Record Delivery' tab to add deliveries.")
        else:
            # KPI Cards
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Total Deliveries", len(df))
            with c2:
                st.metric("Accurate", len(df[df['status'] == '✅ Accurate']))
            with c3:
                st.metric("Short Shipped", len(df[df['status'] == '⚠️ Short Shipped']))
            with c4:
                total_impact = df['financial_impact'].sum()
                st.metric("Financial Impact", f"LKR {abs(total_impact):,.2f}")

            st.markdown("---")

            # Chart
            st.markdown("**Delivery Status**")
            status_counts = df['status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            fig = px.pie(status_counts, values='Count', names='Status', hole=0.35)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
           

    # =========================================================
    # TAB 2: RECORD DELIVERY
    # =========================================================
    with tab2:
        st.markdown('<div class="section-title">📦 Record New Delivery</div>', unsafe_allow_html=True)

        if conn_type == "supabase":
            suppliers_df = pd.DataFrame(conn.table("suppliers").select("*").execute().data)
            products_df = get_products_from_catalog()
        else:
            suppliers_df = get_suppliers_sqlite()
            products_df = get_products_sqlite()

        if suppliers_df.empty or products_df.empty:
            st.warning("⚠️ Please add suppliers and products first.")
            st.info("If Hamdhan has added them, they should appear here. Check database connection.")
        else:
            st.success(f"✅ Found {len(suppliers_df)} suppliers and {len(products_df)} products")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                order_num = st.text_input("Order/Invoice Number *")
                supplier_names = suppliers_df['supplier_name'].tolist()
                supplier = st.selectbox("Supplier *", supplier_names)
                del_date = st.date_input("Delivery Date", value=date.today())
            with col_f2:
                product_names = products_df['product_name'].tolist()
                product = st.selectbox("Product *", product_names)
                ordered_qty = st.number_input("Ordered Quantity", min_value=0, value=100, step=10)
                received_qty = st.number_input("Received Quantity", min_value=0, value=100, step=10)

            disc_qty = received_qty - ordered_qty
            disc_pct = (disc_qty / ordered_qty * 100) if ordered_qty > 0 else 0
            _, _, status = detector.calculate_discrepancy(ordered_qty, received_qty)

            st.markdown("---")
            pc1, pc2, pc3 = st.columns(3)
            pc1.metric("Discrepancy", f"{disc_qty:+.0f} units")
            pc2.metric("Percentage", f"{disc_pct:+.1f}%")
            pc3.metric("Status", status)

            if st.button("💾 Save Delivery", type="primary", use_container_width=True):
                if not order_num:
                    st.error("Please enter an order number.")
                elif ordered_qty == 0:
                    st.error("Ordered quantity cannot be zero.")
                else:
                    try:
                        selected_supplier = suppliers_df[suppliers_df['supplier_name'] == supplier].iloc[0]
                        supplier_id = selected_supplier['supplier_id']
                        
                        selected_product = products_df[products_df['product_name'] == product].iloc[0]
                        product_code = selected_product['product_code']
                        unit_price = selected_product.get('unit_price', 0)
                        financial_impact = disc_qty * unit_price

                        if conn_type == "supabase":
                            delivery_result = conn.table("deliveries").insert({
                                "supplier_id": supplier_id,
                                "invoice_number": order_num, 
                                "delivery_date": del_date.isoformat()
                            }).execute()
                            
                            if delivery_result.data:
                                delivery_id = delivery_result.data[0]['delivery_id']
                                conn.table("delivery_items").insert({
                                    "delivery_id": delivery_id, 
                                    "product_code": product_code,
                                    "billed_quantity": ordered_qty, 
                                    "received_quantity": received_qty
                                }).execute()
                            st.success("✅ Delivery recorded successfully!")
                            st.balloons()
                            st.rerun()
                        else:
                            db_conn = sqlite3.connect('supermarket.db')
                            cursor = db_conn.cursor()
                            cursor.execute("""
                                INSERT INTO deliveries (order_number, supplier_id, product_code, ordered_quantity, 
                                                        received_quantity, delivery_date, discrepancy_quantity, 
                                                        discrepancy_percentage, financial_impact, notes)
                                VALUES (?,?,?,?,?,?,?,?,?,?)
                            """, (order_num, supplier_id, product_code, ordered_qty, received_qty, 
                                  del_date.strftime('%Y-%m-%d'), disc_qty, round(disc_pct, 1), financial_impact, ""))
                            db_conn.commit()
                            db_conn.close()
                            st.success("✅ Delivery recorded successfully!")
                            st.balloons()
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error saving delivery: {e}")

        # =========================================================
    # TAB 3: ORDER RECONCILIATION
    # =========================================================
    with tab3:
        st.markdown('<div class="section-title">📊 Order vs Received Reconciliation</div>', unsafe_allow_html=True)
        st.markdown("Track discrepancies and automatically adjust future orders")
        
        # Date Range Selector
        col1, col2 = st.columns(2)
        with col1:
            rec_start_date = st.date_input("From Date", value=date.today() - timedelta(days=90), key="rec_start")
        with col2:
            rec_end_date = st.date_input("To Date", value=date.today(), key="rec_end")
        
        # Load data
        rec_df = get_delivery_data_for_reconciliation(rec_start_date, rec_end_date)
        
        if rec_df.empty:
            st.info("No delivery data found for the selected period.")
        else:
            # =========================================================
            # SECTION 1: SUMMARY CARDS (ADD THIS)
            # =========================================================
            st.markdown("## 📊 Discrepancy Summary")
            
            total_ordered = rec_df['ordered'].sum()
            total_received = rec_df['received'].sum()
            total_discrepancy = total_received - total_ordered
            total_financial = rec_df['financial_impact'].sum()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Ordered", f"{total_ordered:,.0f} units")
            with col2:
                st.metric("Total Received", f"{total_received:,.0f} units")
            with col3:
                st.metric("Net Discrepancy", f"{total_discrepancy:+,.0f} units",
                          delta=f"{total_discrepancy:+,.0f}")
            with col4:
                st.metric("Financial Impact", f"LKR {total_financial:+,.2f}",
                          delta=f"LKR {total_financial:+,.2f}",
                          delta_color="inverse")
            
                       
            
            # =========================================================
            # SECTION 3: SUPPLIER RECONCILIATION (YOUR CODE)
            # =========================================================
            st.markdown("## 🏭 Supplier Reconciliation")
            
            suppliers_list = rec_df['supplier'].unique().tolist()
            selected_supplier = st.selectbox("Select Supplier for Reconciliation", ["All Suppliers"] + suppliers_list)
            
            if selected_supplier != "All Suppliers":
                filtered_df = rec_df[rec_df['supplier'] == selected_supplier]
            else:
                filtered_df = rec_df
            
            adjustments_df = calculate_next_order_adjustment(filtered_df)
            
            if adjustments_df is not None and not adjustments_df.empty:
                st.markdown("### 📋 Recommended Next Order Adjustments")
                
                display_adjustments = adjustments_df[[
                    'product', 'cumulative_shortage', 'cumulative_overage', 
                    'net_position', 'adjustment_type', 'action'
                ]].copy()
                
                display_adjustments.columns = [
                    'Product', 'Cumulative Short', 'Cumulative Over', 
                    'Net Position', 'Adjustment Type', 'Recommended Action'
                ]
                
                st.dataframe(display_adjustments, use_container_width=True)
                
                total_shortage = adjustments_df['cumulative_shortage'].sum()
                total_credit = adjustments_df['cumulative_overage'].sum()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"📦 **Total Shortage to Compensate:** {total_shortage:,.0f} units")
                with col2:
                    st.success(f"💰 **Total Credit Available:** {total_credit:,.0f} units")
                with col3:
                    net_adjustment = total_shortage - total_credit
                    if net_adjustment > 0:
                        st.warning(f"⚖️ **Net Additional Needed:** {net_adjustment:,.0f} units")
                    else:
                        st.success(f"⚖️ **Net Credit Available:** {abs(net_adjustment):,.0f} units")
            else:
                st.info("No adjustments needed for the selected supplier(s)")