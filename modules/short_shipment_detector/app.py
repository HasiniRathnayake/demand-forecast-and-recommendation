<<<<<<< HEAD
# pages/short_shipment_page.py
import streamlit as st
import sys
import os
=======
import streamlit as st
>>>>>>> origin/main
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
<<<<<<< HEAD
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


def send_supplier_alert_outlook(supplier_email, supplier_name, alert_type, details):
    """Send email using Outlook/Hotmail"""

    test_mode = True
    if test_mode:
        supplier_email = "hashiniwickramathilaka@gmail.com"

    # IMPORTANT: Replace these with YOUR actual Outlook credentials
    sender_email = "your_email@outlook.com"  # CHANGE THIS to your actual email
    sender_password = "your_actual_password"  # CHANGE THIS to your actual password

    # Don't use MIMEMultipart if you only need text
    msg = MIMEText(f"""
    Dear {supplier_name},

    Alert Type: {alert_type}
    Details: {details}

    Please investigate and ensure accurate deliveries.

    Regards,
    Short-Shipment Detection System
    SUNRISE Super
    """)

    msg['From'] = sender_email
    msg['To'] = supplier_email
    msg['Subject'] = f"⚠️ Alert: {alert_type} Detected - {supplier_name}"

    try:
        # Outlook/Hotmail SMTP settings
        server = smtplib.SMTP('smtp-mail.outlook.com', 587)
        server.ehlo()  # Identify to server
        server.starttls()  # Start encryption
        server.ehlo()  # Re-identify after TLS
        server.login(sender_email, sender_password)  # Login
        server.send_message(msg)  # Send email
        server.quit()  # Close connection

        print(f"✅ Email sent successfully via Outlook to {supplier_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("   Check your email and password")
        return False

    except smtplib.SMTPException as e:
        print(f"❌ SMTP error: {e}")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


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

=======
from streamlit_option_menu import option_menu
import sqlite3
import numpy as np
import io
import base64

# Import local modules
from database import get_db_connection, init_database, add_sample_data
from detectors import ShortShipmentDetector
from utils import *
from style import load_css

# Page configuration
st.set_page_config(
    page_title="Short-Shipment Detector",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize theme in session state FIRST
if 'theme' not in st.session_state:
    st.session_state.theme = "dark"

# Initialize database
init_database()
detector = ShortShipmentDetector()

# Helper functions to detect connection type
def is_supabase(conn):
    return hasattr(conn, 'table') and callable(getattr(conn, 'table'))

def is_sqlite(conn):
    return hasattr(conn, 'cursor') and hasattr(conn, 'execute')

# Supabase data fetching functions
def get_deliveries_supabase(conn, start_date, end_date):
    """Fetch deliveries from Supabase"""
    try:
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        response = conn.table("deliveries")\
            .select("""
                delivery_id,
                invoice_number,
                delivery_date,
                supplier_id,
                suppliers!inner(
                    supplier_name,
                    contact_number,
                    email
                ),
                delivery_items(
                    delivery_item_id,
                    product_code,
                    billed_quantity,
                    received_quantity,
                    products!inner(
                        product_name,
                        category,
                        cost_price,
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
            supplier_name = delivery.get('suppliers', {}).get('supplier_name', 'Unknown')
            
            for item in delivery.get('delivery_items', []):
                product_info = item.get('products', {})
                
                billed = float(item.get('billed_quantity', 0))
                received = float(item.get('received_quantity', 0))
                discrepancy = received - billed
                disc_pct = (discrepancy / billed * 100) if billed > 0 else 0
                
                row = {
                    'delivery_date': delivery.get('delivery_date'),
                    'invoice_number': delivery.get('invoice_number'),
                    'supplier_name': supplier_name,
                    'product_name': product_info.get('product_name', 'Unknown'),
                    'category': product_info.get('category', 'Unknown'),
                    'cost_price': float(product_info.get('cost_price', 0)),
                    'ordered_quantity': billed,
                    'received_quantity': received,
                    'discrepancy_quantity': discrepancy,
                    'discrepancy_percentage': round(disc_pct, 1),
                    'financial_impact': discrepancy * float(product_info.get('cost_price', 0))
                }
                data.append(row)
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error fetching from Supabase: {e}")
        return pd.DataFrame()

def get_suppliers_supabase(conn):
    """Fetch suppliers from Supabase"""
    try:
        response = conn.table("suppliers").select("*").order("supplier_name").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching suppliers: {e}")
        return pd.DataFrame()

def get_products_supabase(conn):
    """Fetch products from Supabase"""
    try:
        response = conn.table("products").select("*").order("product_name").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching products: {e}")
        return pd.DataFrame()

# SQLite helper functions
def get_suppliers_sqlite():
    """Get suppliers from SQLite"""
    conn = sqlite3.connect('supermarket.db')
    df = pd.read_sql_query("SELECT * FROM suppliers ORDER BY supplier_name", conn)
    conn.close()
    return df

def get_products_sqlite():
    """Get products from SQLite"""
    conn = sqlite3.connect('supermarket.db')
    df = pd.read_sql_query("SELECT * FROM products ORDER BY product_name", conn)
    conn.close()
    return df

# Main database connection
conn = get_db_connection()
conn_type = "supabase" if is_supabase(conn) else "sqlite" if is_sqlite(conn) else "unknown"

# Alert function
def check_for_alerts(conn, conn_type):
    alerts = []
    try:
        if conn_type == "supabase":
            seven_days_ago = (date.today() - timedelta(days=7)).isoformat()
            response = conn.table("deliveries")\
                .select("*, suppliers!inner(supplier_name), products!inner(product_name)")\
                .gte("delivery_date", seven_days_ago)\
                .execute()
            
            for item in response.data:
                if abs(item.get('discrepancy_percentage', 0)) > 20:
                    alerts.append({
                        'type': 'danger',
                        'message': f"Large discrepancy: {item['suppliers']['supplier_name']} - {item['products']['product_name']} ({item['discrepancy_percentage']:+.1f}%)"
                    })
    except Exception as e:
        print(f"Alert error: {e}")
    return alerts

# ============================================
# SIDEBAR with Theme Toggle
# ============================================
with st.sidebar:
    st.markdown("###  Navigation")
    
    selected = option_menu(
    menu_title=None,
    options=["Dashboard", "Record Delivery", "Suppliers", "Products", 
             "Analytics", "Product Performance"],
    menu_icon="cast",
    default_index=0,
    styles={
        "container": {"padding": "0!important", "background-color": "transparent"},
        "icon": {"color": "#667eea", "font-size": "20px"},
        "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px", "color": "#666"},
        "nav-link-selected": {"background-color": "#667eea", "color": "white"},
    }
)
    
    st.markdown("---")
    
    # Quick stats
    temp_conn = get_db_connection()
    try:
        if is_sqlite(temp_conn):
            cursor = temp_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM suppliers")
            total_suppliers = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM products")
            total_products = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM deliveries")
            total_deliveries = cursor.fetchone()[0]
        elif is_supabase(temp_conn):
            suppliers_resp = temp_conn.table("suppliers").select("*", count="exact").execute()
            products_resp = temp_conn.table("products").select("*", count="exact").execute()
            deliveries_resp = temp_conn.table("deliveries").select("*", count="exact").execute()
            total_suppliers = len(suppliers_resp.data) if suppliers_resp.data else 0
            total_products = len(products_resp.data) if products_resp.data else 0
            total_deliveries = len(deliveries_resp.data) if deliveries_resp.data else 0
        else:
            total_suppliers = total_products = total_deliveries = 0
        
        st.markdown("###  Quick Stats")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Suppliers", total_suppliers)
            st.metric("Products", total_products)
        with col2:
            st.metric("Deliveries", total_deliveries)
    except Exception as e:
        st.error(f"Error loading stats: {e}")
    finally:
        if is_sqlite(temp_conn):
            temp_conn.close()
    
    st.markdown("---")
    
    # ============================================
    # THEME TOGGLE (Light/Dark Mode)
    # ============================================
    st.markdown("### Appearance")
    col_theme1, col_theme2 = st.columns(2)
    with col_theme1:
        if st.button(" Dark Mode", use_container_width=True):
            st.session_state.theme = "dark"
            st.rerun()
    with col_theme2:
        if st.button(" Light Mode", use_container_width=True):
            st.session_state.theme = "light"
            st.rerun()
    
    # Show current theme
    if st.session_state.theme == "dark":
        st.sidebar.success(" Dark Mode Active")
    else:
        st.sidebar.success("Light Mode Active")
    
    st.markdown("---")
        
    st.markdown("""
        <div style="text-align: center; color: #666; font-size: 0.8rem; margin-top: 2rem;">
            Connected to Forecasting Module
        </div>
    """, unsafe_allow_html=True)

# Load CSS with selected theme
st.markdown(load_css(st.session_state.theme), unsafe_allow_html=True)

# Custom header
st.markdown("""
    <div class="main-header">
        <h1> Short-Shipment Detection System</h1>
        <p style="opacity: 0.9;">Real-time discrepancy monitoring & supplier performance analytics</p>
    </div>
""", unsafe_allow_html=True)

# ============================================
# DASHBOARD PAGE
# ============================================
if selected == "Dashboard":
    # Date filter
    col1, col2, col3 = st.columns([2, 2, 4])
    with col1:
        start_date = st.date_input("From", value=date(2026, 1, 1))
    with col2:
        end_date = st.date_input("To", value=date(2026, 12, 31))
    
    try:
        if conn_type == "supabase":
            df = get_deliveries_supabase(conn, start_date, end_date)
        elif conn_type == "sqlite":
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            query = """
                SELECT 
                    d.delivery_date,
                    d.order_number as invoice_number,
                    s.supplier_name,
                    p.product_name,
                    p.cost_price,
                    d.ordered_quantity,
                    d.received_quantity,
                    d.discrepancy_quantity,
                    d.discrepancy_percentage,
                    d.financial_impact
                FROM deliveries d
                LEFT JOIN suppliers s ON d.supplier_id = s.supplier_id
                LEFT JOIN products p ON d.product_code = p.product_code
                WHERE date(d.delivery_date) BETWEEN date(?) AND date(?)
                ORDER BY d.delivery_date DESC
            """
            df = pd.read_sql_query(query, conn, params=[start_str, end_str])
        else:
            df = pd.DataFrame()
    except Exception as e:
        st.error(f"Database error: {e}")
        df = pd.DataFrame()
    
    if not df.empty:
        st.success(f" Found {len(df)} deliveries!")
        
        # Calculate derived fields
        if 'discrepancy_quantity' not in df.columns:
            df['discrepancy_quantity'] = df['received_quantity'] - df['ordered_quantity']
        if 'discrepancy_percentage' not in df.columns:
            df['discrepancy_percentage'] = ((df['received_quantity'] - df['ordered_quantity']) / df['ordered_quantity'] * 100).round(1)
        if 'financial_impact' not in df.columns:
            df['financial_impact'] = df['discrepancy_quantity'] * df['cost_price']
        
        # Determine status
        conditions = [
            abs(df['discrepancy_quantity']) < 0.01,
            df['discrepancy_quantity'] < 0,
            df['discrepancy_quantity'] > 0
        ]
        choices = [' Accurate', ' Short Shipped', ' Over Delivered']
        df['status'] = np.select(conditions, choices, default='Unknown')
        
        # KPI Metrics
        st.markdown('<div class="section-header"> Key Performance Indicators</div>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        total_deliveries = len(df)
        total_discrepancies = len(df[df['status'] != ' Accurate'])
        total_financial = df['financial_impact'].sum()
        accuracy = ((total_deliveries - total_discrepancies) / total_deliveries * 100) if total_deliveries > 0 else 0
        
        with col1:
            st.metric("Total Deliveries", total_deliveries)
        with col2:
            st.metric("Discrepancies Found", total_discrepancies)
        with col3:
            st.metric("Accuracy Rate", f"{accuracy:.1f}%")
        
        # Ordered vs Received Analysis Tabs
        st.markdown('<div class="section-header"> Ordered vs Received Quantity Analysis</div>', unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs([" Comparison Table", " Bar Chart"])
        
        # TAB 1: COMPARISON TABLE
        with tab1:
            comparison_df = df[['delivery_date', 'invoice_number', 'supplier_name', 'product_name', 
                               'ordered_quantity', 'received_quantity', 'status']].copy()
            
            if not comparison_df.empty:
                st.subheader(f"Showing {len(comparison_df)} items")
                
                comparison_df['variance'] = comparison_df['received_quantity'] - comparison_df['ordered_quantity']
                comparison_df['ordered_quantity'] = comparison_df['ordered_quantity'].apply(lambda x: f"{x:,.0f}")
                comparison_df['received_quantity'] = comparison_df['received_quantity'].apply(lambda x: f"{x:,.0f}")
                
                comparison_df.columns = [
                    'Date', 'Invoice', 'Supplier', 'Product',
                    'Ordered', 'Received', 'Status', 'Variance Qty'
                ]
                comparison_df = comparison_df.drop('Variance Qty', axis=1)
                
                def color_status(val):
                    if 'Short' in str(val):
                        return 'background-color: #ffcccc'
                    elif 'Over' in str(val):
                        return 'background-color: #cce5ff'
                    elif 'Accurate' in str(val):
                        return 'background-color: #d4edda'
                    return ''
                
                st.dataframe(
                    comparison_df.style.map(color_status, subset=['Status']),
                    width='stretch',
                    height=400
                )
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Ordered", f"{df['ordered_quantity'].sum():,.0f}")
                with col2:
                    st.metric("Total Received", f"{df['received_quantity'].sum():,.0f}")
                with col3:
                    acc = len(df[df['status'] == ' Accurate']) / len(df) * 100
                    st.metric("Order Accuracy", f"{acc:.1f}%")
            else:
                st.info("No data available")
        
        # TAB 2: BAR CHART
        with tab2:
            if not df.empty:
                chart_df = df[['invoice_number', 'product_name', 'ordered_quantity', 'received_quantity']].head(15).copy()
                chart_df['label'] = chart_df['invoice_number'] + ' - ' + chart_df['product_name']
                
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Ordered', x=chart_df['label'], y=chart_df['ordered_quantity'], marker_color='#3498db', text=chart_df['ordered_quantity'].round(0), textposition='auto'))
                fig.add_trace(go.Bar(name='Received', x=chart_df['label'], y=chart_df['received_quantity'], marker_color='#2ecc71', text=chart_df['received_quantity'].round(0), textposition='auto'))
                fig.update_layout(title='Ordered vs Received by Invoice', barmode='group', height=500, xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
                st.caption(" Blue = Ordered | Green = Received")
            else:
                st.info("No data available")
        
        # Discrepancy Distribution Pie Chart (Line chart removed)
        st.markdown('<div class="section-header"> Discrepancy Distribution</div>', unsafe_allow_html=True)
        
        status_counts = df['status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig = px.pie(status_counts, values='Count', names='Status', title='Discrepancy Distribution',
                    color='Status', color_discrete_map={' Accurate': '#28a745', ' Short Shipped': '#dc3545', ' Over Delivered': '#17a2b8'})
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
        
        # Recent Deliveries Table
        st.markdown('<div class="section-header"> Recent Deliveries</div>', unsafe_allow_html=True)
        
        display_df = df[['delivery_date', 'invoice_number', 'supplier_name', 'product_name', 
                        'ordered_quantity', 'received_quantity', 'status']].head(10).copy()
        display_df['ordered_quantity'] = display_df['ordered_quantity'].apply(lambda x: f"{x:,.0f}")
        display_df['received_quantity'] = display_df['received_quantity'].apply(lambda x: f"{x:,.0f}")
        st.dataframe(display_df, width='stretch')
        
    else:
        st.warning("No data available for selected date range")
        
        
    

####################
# RECORD DELIVERY PAGE
####################
elif selected == "Record Delivery":
    st.markdown('<div class="section-header"> Record New Delivery</div>', unsafe_allow_html=True)
    
    # Get suppliers and products based on connection type
    if conn_type == "supabase":
        suppliers_df = get_suppliers_supabase(conn)
        products_df = get_products_supabase(conn)
    elif conn_type == "sqlite":
        suppliers_df = get_suppliers_sqlite() if 'get_suppliers_sqlite' in dir() else pd.DataFrame()
        products_df = get_products_sqlite() if 'get_products_sqlite' in dir() else pd.DataFrame()
    else:
        suppliers_df = pd.DataFrame()
        products_df = pd.DataFrame()
    
    if suppliers_df.empty or products_df.empty:
        st.warning("⚠️ Please add suppliers and products first using the Suppliers and Products pages!")
    else:
        with st.form("delivery_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("####  Delivery Info")
                invoice_number = st.text_input("Invoice Number *", placeholder="e.g., INV-004")
                supplier_id = st.selectbox(
                    "Supplier *",
                    options=suppliers_df['supplier_id'].tolist(),
                    format_func=lambda x: f"{x} - {suppliers_df[suppliers_df['supplier_id'] == x]['supplier_name'].iloc[0]}"
                )
                delivery_date = st.date_input("Delivery Date *", value=date.today())
            
            with col2:
                st.markdown("####  Product Info")
                product_code = st.selectbox(
                    "Product *",
                    options=products_df['product_code'].tolist(),
                    format_func=lambda x: f"{products_df[products_df['product_code'] == x]['product_name'].iloc[0]} (LKR {products_df[products_df['product_code'] == x]['unit_price'].iloc[0]:.2f})"
                )
                
                selected_product = products_df[products_df['product_code'] == product_code].iloc[0]
                
                col_a, col_b = st.columns(2)
                with col_a:
                    billed_qty = st.number_input("Billed Quantity *", min_value=0.0, step=1.0, value=100.0)
                with col_b:
                    received_qty = st.number_input("Received Quantity *", min_value=0.0, step=1.0, value=100.0)
                
                notes = st.text_area("Notes", placeholder="Any additional notes...")
            
            # Preview discrepancy
            if billed_qty > 0:
                disc_qty = received_qty - billed_qty
                disc_pct = (disc_qty / billed_qty) * 100
                
                st.markdown("####  Discrepancy Preview")
                
                if abs(disc_qty) < 0.01:
                    st.success(" Order will be marked as ACCURATE")
                elif disc_qty < 0:
                    financial = disc_qty * selected_product['cost_price']
                    st.error(f" SHORT SHIPMENT: Missing {abs(disc_qty)} units ({disc_pct:.1f}%) - Loss: LKR {abs(financial):.2f}")
                else:
                    financial = disc_qty * selected_product['cost_price']
                    st.warning(f" OVER DELIVERY: Extra {disc_qty} units ({disc_pct:.1f}%) - Extra Cost: LKR {financial:.2f}")
            
            submitted = st.form_submit_button(" Record Delivery", use_container_width=True)
            
            if submitted:
                if not invoice_number:
                    st.error("Invoice number is required!")
                else:
                    try:
                        if conn_type == "supabase":
                            # Insert into deliveries table
                            delivery_data = {
                                "supplier_id": supplier_id,
                                "invoice_number": invoice_number,
                                "delivery_date": delivery_date.isoformat()
                            }
                            delivery_result = conn.table("deliveries").insert(delivery_data).execute()
                            
                            if delivery_result.data:
                                delivery_id = delivery_result.data[0]['delivery_id']
                                
                                # Insert into delivery_items table
                                item_data = {
                                    "delivery_id": delivery_id,
                                    "product_code": product_code,
                                    "billed_quantity": billed_qty,
                                    "received_quantity": received_qty
                                }
                                conn.table("delivery_items").insert(item_data).execute()
                                
                                st.balloons()
                                st.success(f"Delivery recorded successfully!")
                                st.rerun()  
                        
                        elif conn_type == "sqlite":
                            # SQLite version
                            cursor = conn.cursor()
                            
                            # Insert into deliveries
                            cursor.execute("""
                                INSERT INTO deliveries (supplier_id, invoice_number, delivery_date)
                                VALUES (?, ?, ?)
                            """, (supplier_id, invoice_number, delivery_date))
                            delivery_id = cursor.lastrowid
                            
                            # Insert into delivery_items
                            cursor.execute("""
                                INSERT INTO delivery_items (delivery_id, product_code, billed_quantity, received_quantity)
                                VALUES (?, ?, ?, ?)
                            """, (delivery_id, product_code, billed_qty, received_qty))
                            
                            conn.commit()
                            st.balloons()
                            st.success(f" Delivery recorded successfully!")
                            st.rerun()  
                            
                    except Exception as e:
                        st.error(f"Error recording delivery: {e}")
####################
# SUPPLIERS PAGE
####################
elif selected == "Suppliers":
    st.markdown('<div class="section-header"> Supplier Management</div>', unsafe_allow_html=True)
    
    # Get existing suppliers
    if conn_type == "supabase":
        suppliers_df = get_suppliers_supabase(conn)
    elif conn_type == "sqlite":
        suppliers_df = get_suppliers_sqlite()
    else:
        suppliers_df = pd.DataFrame()
    
    # Get existing supplier IDs for duplicate check
    existing_ids = suppliers_df['supplier_id'].tolist() if not suppliers_df.empty else []
    
    # Display existing suppliers
    if not suppliers_df.empty:
        st.subheader(" Current Suppliers")
        
        if conn_type == "supabase":
            display_df = suppliers_df[['supplier_id', 'supplier_name', 'contact_number', 'email']].copy()
            display_df.columns = ['Supplier ID', 'Name', 'Contact Number', 'Email']
            st.dataframe(display_df, width='stretch')
            st.caption(f"Total: {len(suppliers_df)} suppliers")
        else:
            st.dataframe(suppliers_df, width='stretch')
    else:
        st.info("No suppliers found. Add your first supplier below!")
    
    st.markdown("---")
    
    # Add new supplier form
    st.subheader("Add New Supplier")
    
    # Session state to store phone number
    if 'phone_input' not in st.session_state:
        st.session_state.phone_input = ""
    
    with st.form("add_supplier_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            supplier_id = st.text_input("Supplier ID *", placeholder="e.g., SUP-004", max_chars=20)
            supplier_name = st.text_input("Supplier Name *", placeholder="e.g., New Supplier Ltd", max_chars=100)
            
            # Phone number input with custom handling
            phone_raw = st.text_input(
                "Contact Number", 
                placeholder="e.g., 0771234567 (10 digits only)",
                help="Enter 10 digits only. No spaces or dashes needed.",
                max_chars=10  #  This limits to 10 characters
            )
        
        with col2:
            email = st.text_input("Email", placeholder="e.g., contact@supplier.com", max_chars=100)
        
        # Show live digit counter
        if phone_raw:
            digits_only = re.sub(r'[^0-9]', '', phone_raw)
            if len(digits_only) == 10:
                st.success(f" {len(digits_only)}/10 digits - Valid phone number")
            elif len(digits_only) > 0:
                st.info(f" {len(digits_only)}/10 digits entered")
            else:
                st.info(" Enter 10 digits")
        
        submitted = st.form_submit_button(" Add Supplier", use_container_width=True)
        
        if submitted:
            errors = []
            
            # Validate Supplier ID
            is_valid, error = validate_supplier_id(supplier_id, existing_ids)
            if not is_valid:
                errors.append(error)
            
            # Validate Supplier Name
            if not supplier_name or not supplier_name.strip():
                errors.append(" Supplier Name is required")
            elif len(supplier_name.strip()) < 3:
                errors.append(" Supplier Name must be at least 3 characters")
            
            # Validate Phone Number
            if phone_raw:
                # Extract only digits
                digits_only = re.sub(r'[^0-9]', '', phone_raw)
                
                if len(digits_only) != 10:
                    errors.append(f" Phone number must have exactly 10 digits. You entered {len(digits_only)} digits.")
                else:
                    # Format the phone number
                    formatted_phone = f"{digits_only[:3]}-{digits_only[3:]}"
            else:
                formatted_phone = None
            
            # Validate Email
            if email:
                is_valid, error = validate_email(email)
                if not is_valid:
                    errors.append(error)
            
            # Show errors or save
            if errors:
                for error in errors:
                    st.error(error)
            else:
                try:
                    if conn_type == "supabase":
                        data = {
                            "supplier_id": supplier_id,
                            "supplier_name": supplier_name,
                            "contact_number": formatted_phone,
                            "email": email if email else None
                        }
                        conn.table("suppliers").insert(data).execute()
                        st.success(f" Supplier '{supplier_name}' added successfully!")
                        st.session_state.phone_input = ""  # Clear input
                        st.rerun()
                    
                    elif conn_type == "sqlite":
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO suppliers (supplier_id, supplier_name, contact_number, email)
                            VALUES (?, ?, ?, ?)
                        """, (supplier_id, supplier_name, formatted_phone, email if email else None))
                        conn.commit()
                        st.success(f" Supplier '{supplier_name}' added successfully!")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error adding supplier: {e}")

####################
# PRODUCTS PAGE
####################
elif selected == "Products":
    st.markdown('<div class="section-header"> Product Management</div>', unsafe_allow_html=True)
    
    # Get suppliers for dropdown
    if conn_type == "supabase":
        suppliers_df = get_suppliers_supabase(conn)
        products_df = get_products_supabase(conn)
    elif conn_type == "sqlite":
        suppliers_df = get_suppliers_sqlite()
        products_df = get_products_sqlite()
    else:
        suppliers_df = pd.DataFrame()
        products_df = pd.DataFrame()
    
    # Get existing product codes for duplicate check
    existing_codes = products_df['product_code'].tolist() if not products_df.empty else []
    
    # Add supplier names to products
    if not products_df.empty and not suppliers_df.empty:
        supplier_dict = dict(zip(suppliers_df['supplier_id'], suppliers_df['supplier_name']))
        if 'supplier_id' in products_df.columns:
            products_df['supplier_name'] = products_df['supplier_id'].map(supplier_dict).fillna('Unknown')
    
    # Display products
    if not products_df.empty:
        st.subheader(" Current Products")
        display_cols = ['product_code', 'product_name']
        if 'supplier_name' in products_df.columns:
            display_cols.append('supplier_name')
        display_cols.extend(['category', 'unit_price', 'cost_price'])
        display_df = products_df[[c for c in display_cols if c in products_df.columns]].copy()
        
        if 'unit_price' in display_df.columns:
            display_df['unit_price'] = display_df['unit_price'].apply(lambda x: f"LKR {x:,.2f}")
        if 'cost_price' in display_df.columns:
            display_df['cost_price'] = display_df['cost_price'].apply(lambda x: f"LKR {x:,.2f}")
        
        st.dataframe(display_df, width='stretch')
        st.caption(f"Total: {len(products_df)} products")
    else:
        st.info("No products found. Add your first product below!")
    
    st.markdown("---")
    
    # Add new product form
    st.subheader(" Add New Product")
    
    with st.form("add_product_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            product_code = st.text_input("Product Code *", placeholder="e.g., P004 or PROD-001")
            product_name = st.text_input("Product Name *", placeholder="e.g., Rice 5kg")
            category = st.selectbox("Category", ["Dairy", "Bakery", "Groceries", "Produce", "Meat", "Beverages", "Other"])
            
            # Supplier dropdown
            if not suppliers_df.empty:
                supplier_options = suppliers_df['supplier_id'].tolist()
                supplier_display = [f"{row['supplier_id']} - {row['supplier_name']}" for _, row in suppliers_df.iterrows()]
                
                selected_index = st.selectbox(
                    "Supplier *",
                    options=range(len(supplier_options)),
                    format_func=lambda x: supplier_display[x] if x < len(supplier_display) else "Unknown"
                )
                selected_supplier = supplier_options[selected_index]
            else:
                st.warning("No suppliers found. Please add suppliers first.")
                selected_supplier = None
        
        with col2:
            unit_price = st.number_input("Unit Price (LKR) *", min_value=0.01, step=10.00, value=100.00)
            cost_price = st.number_input("Cost Price (LKR) *", min_value=0.01, step=10.00, value=80.00)
        
        submitted = st.form_submit_button(" Add Product", use_container_width=True)
        
        if submitted:
            errors = []
            
            # Validate Product Code
            is_valid, error = validate_product_code(product_code, existing_codes)
            if not is_valid:
                errors.append(error)
            
            # Validate Product Name
            if not product_name or not product_name.strip():
                errors.append(" Product Name is required")
            elif len(product_name.strip()) < 3:
                errors.append(" Product Name must be at least 3 characters")
            
            # Validate Prices
            if unit_price <= 0:
                errors.append("Unit Price must be greater than zero")
            if cost_price <= 0:
                errors.append(" Cost Price must be greater than zero")
            if cost_price > unit_price:
                errors.append(" Warning: Cost Price is higher than Unit Price")
            
            # Validate Supplier
            if selected_supplier is None and not suppliers_df.empty:
                errors.append(" Please select a supplier")
            
            # Show errors or save
            if errors:
                for error in errors:
                    st.error(error)
            else:
                try:
                    if conn_type == "supabase":
                        data = {
                            "product_code": product_code,
                            "product_name": product_name,
                            "category": category,
                            "unit_price": unit_price,
                            "cost_price": cost_price,
                            "supplier_id": selected_supplier
                        }
                        conn.table("products").insert(data).execute()
                        st.success(f" Product '{product_name}' added successfully!")
                        st.rerun()
                    
                    elif conn_type == "sqlite":
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO products (product_code, product_name, category, unit_price, cost_price, supplier_id)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (product_code, product_name, category, unit_price, cost_price, selected_supplier))
                        conn.commit()
                        st.success(f" Product '{product_name}' added successfully!")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error adding product: {e}")
####################
# ANALYTICS PAGE
####################
elif selected == "Analytics":
    st.markdown('<div class="section-header"> AI-Powered Analytics</div>', unsafe_allow_html=True)
    st.caption("Machine learning insights and predictive analytics for supply chain optimization")
    
    # Create tabs for different analytics views
    tab1, tab2  = st.tabs([
        "Supplier Risk Analysis", 
        "Shipment Predictions"
        
    ])
    
    # ============================================
    # TAB 1: SUPPLIER RISK ANALYSIS
    # ============================================
    with tab1:
        st.subheader("Supplier Risk Assessment")
        
        try:
            if conn_type == "supabase":
                # Fetch deliveries
                deliveries_resp = conn.table("deliveries").select("*").execute()
                items_resp = conn.table("delivery_items").select("*").execute()
                products_resp = conn.table("products").select("*").execute()
                suppliers_resp = conn.table("suppliers").select("*").execute()
                
                if deliveries_resp.data and items_resp.data:
                    # Create lookup dictionaries
                    product_dict = {p['product_code']: p for p in products_resp.data}
                    supplier_dict = {s['supplier_id']: s['supplier_name'] for s in suppliers_resp.data}
                    
                    # Group items by delivery
                    items_by_delivery = {}
                    for item in items_resp.data:
                        did = item.get('delivery_id')
                        if did not in items_by_delivery:
                            items_by_delivery[did] = []
                        items_by_delivery[did].append(item)
                    
                    # Calculate supplier stats
                    supplier_stats = {}
                    for delivery in deliveries_resp.data:
                        did = delivery.get('delivery_id')
                        supplier_id = delivery.get('supplier_id')
                        items = items_by_delivery.get(did, [])
                        
                        if supplier_id not in supplier_stats:
                            supplier_stats[supplier_id] = {
                                'name': supplier_dict.get(supplier_id, 'Unknown'),
                                'deliveries': 0,
                                'short_items': 0,
                                'total_ordered': 0,
                                'total_received': 0,
                                'loss': 0
                            }
                        
                        supplier_stats[supplier_id]['deliveries'] += 1
                        
                        for item in items:
                            billed = float(item.get('billed_quantity', 0))
                            received = float(item.get('received_quantity', 0))
                            product_code = item.get('product_code')
                            product = product_dict.get(product_code, {})
                            cost = float(product.get('cost_price', 0))
                            
                            supplier_stats[supplier_id]['total_ordered'] += billed
                            supplier_stats[supplier_id]['total_received'] += received
                            
                            if received < billed:
                                supplier_stats[supplier_id]['short_items'] += 1
                                supplier_stats[supplier_id]['loss'] += (billed - received) * cost
                    
                    if supplier_stats:
                        risk_data = []
                        for sid, stats in supplier_stats.items():
                            total_deliveries = stats['deliveries']
                            short_rate = (stats['short_items'] / total_deliveries * 100) if total_deliveries > 0 else 0
                            accuracy = 100 - short_rate
                            
                            # Calculate risk score
                            risk_score = short_rate * 0.6 + min(stats['loss'] / 10000, 40) * 0.4
                            risk_score = min(risk_score, 100)
                            
                            if risk_score >= 70:
                                risk_level = "HIGH RISK"
                            elif risk_score >= 40:
                                risk_level = "MEDIUM RISK"
                            else:
                                risk_level = "LOW RISK"
                            
                            risk_data.append({
                                'Supplier': stats['name'],
                                'Deliveries': total_deliveries,
                                'Short Items': stats['short_items'],
                                'Short Rate %': round(short_rate, 1),
                                'Accuracy %': round(accuracy, 1),
                                'Loss (LKR)': f"LKR {stats['loss']:,.2f}",
                                'Risk Score': round(risk_score, 1),
                                'Risk Level': risk_level
                            })
                        
                        risk_df = pd.DataFrame(risk_data)
                        st.dataframe(risk_df, width='stretch')
                        
                        # Risk distribution chart
                        high_count = sum(1 for r in risk_data if r['Risk Level'] == 'HIGH RISK')
                        medium_count = sum(1 for r in risk_data if r['Risk Level'] == 'MEDIUM RISK')
                        low_count = sum(1 for r in risk_data if r['Risk Level'] == 'LOW RISK')
                        
                        fig = px.pie(
                            values=[high_count, medium_count, low_count],
                            names=['High Risk', 'Medium Risk', 'Low Risk'],
                            title='Supplier Risk Distribution',
                            color=['High Risk', 'Medium Risk', 'Low Risk'],
                            color_discrete_map={'High Risk': '#dc3545', 'Medium Risk': '#ffc107', 'Low Risk': '#28a745'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No supplier data available")
                else:
                    st.info("No delivery data available")
            
            elif conn_type == "sqlite":
                query = """
                    SELECT 
                        s.supplier_name,
                        COUNT(DISTINCT d.delivery_id) as deliveries,
                        SUM(CASE WHEN di.received_quantity < di.billed_quantity THEN 1 ELSE 0 END) as short_items,
                        SUM((di.billed_quantity - di.received_quantity) * p.cost_price) as total_loss
                    FROM suppliers s
                    LEFT JOIN deliveries d ON s.supplier_id = d.supplier_id
                    LEFT JOIN delivery_items di ON d.delivery_id = di.delivery_id
                    LEFT JOIN products p ON di.product_code = p.product_code
                    GROUP BY s.supplier_id
                    HAVING deliveries > 0
                """
                df = pd.read_sql_query(query, conn)
                
                if not df.empty:
                    df['Short Rate %'] = (df['short_items'] / df['deliveries'] * 100).round(1)
                    df['Accuracy %'] = (100 - df['Short Rate %']).round(1)
                    st.dataframe(df, width='stretch')
                else:
                    st.info("No data available")
                    
        except Exception as e:
            st.error(f"Error loading data: {e}")
            st.info("Please add deliveries to see analytics")
    
    # ============================================
    # TAB 2: SHIPMENT PREDICTIONS
    # ============================================
    with tab2:
        st.subheader("Shipment Predictions")
        st.info("Based on historical patterns and seasonal trends")
        
        
        st.metric("Next 7 Days", "8-12 shipments")
        
        st.markdown("---")
        st.subheader("Prediction Factors")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Seasonal Factors**")
            st.markdown("- Peak season: March, December")
            st.markdown("- Low season: April, August")
        with col2:
            st.markdown("**Risk Factors**")
            st.markdown("- Supplier reliability: 78% average")
            st.markdown("- Historical shortage rate: 25%")
    
    
                        


# ============================================
# PRODUCT PERFORMANCE PAGE
# ============================================
elif selected == "Product Performance":
    st.markdown('<div class="section-header"> Product Performance Analysis</div>', unsafe_allow_html=True)
    st.caption("Analyze discrepancy patterns and performance metrics by product")
    
    # ============================================
    # GET DATA
    # ============================================
    try:
        if conn_type == "supabase":
            # Fetch data from Supabase
            deliveries_response = conn.table("deliveries").select("*").execute()
            items_response = conn.table("delivery_items").select("*").execute()
            products_response = conn.table("products").select("*").execute()
            suppliers_response = conn.table("suppliers").select("*").execute()
            
            # Create lookup dictionaries
            product_dict = {p['product_code']: p for p in products_response.data}
            supplier_dict = {s['supplier_id']: s['supplier_name'] for s in suppliers_response.data}
            
            # Combine data
            data = []
            for delivery in deliveries_response.data:
                supplier_name = supplier_dict.get(delivery.get('supplier_id'), 'Unknown')
                for item in items_response.data:
                    if item['delivery_id'] == delivery['delivery_id']:
                        product = product_dict.get(item['product_code'], {})
>>>>>>> origin/main
                        data.append({
                            'delivery_date': delivery.get('delivery_date'),
                            'invoice_number': delivery.get('invoice_number'),
                            'supplier_name': supplier_name,
<<<<<<< HEAD
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
    # Function to ensure sample data exists
    # =========================================================
    def ensure_sample_data():
        """Check if data exists, only add if absolutely necessary"""
        try:
            if conn_type == "supabase":
                suppliers = pd.DataFrame(conn.table("suppliers").select("*").limit(1).execute().data)
                products = pd.DataFrame(conn.table("product_catalog").select("*").limit(1).execute().data)

                if not suppliers.empty and not products.empty:
                    st.success(f"✅ Using existing data from database")
                    return True
            else:
                suppliers = get_suppliers_sqlite()
                products = get_products_sqlite()
                if not suppliers.empty and not products.empty:
                    return True
        except:
            suppliers = pd.DataFrame()
            products = pd.DataFrame()

        if suppliers.empty:
            st.info("📦 Adding sample suppliers...")
            sample_suppliers = [
                {"supplier_id": "SUP001", "supplier_name": "Fresh Foods Ltd", "contact_number": "077-1234567", "email": "fresh@foods.lk"},
                {"supplier_id": "SUP002", "supplier_name": "Bakery Express", "contact_number": "077-2345678", "email": "bakery@express.lk"},
                {"supplier_id": "SUP003", "supplier_name": "Global Grocers", "contact_number": "077-3456789", "email": "global@grocers.lk"},
            ]
            try:
                if conn_type == "supabase":
                    for sup in sample_suppliers:
                        conn.table("suppliers").insert(sup).execute()
                else:
                    db_conn = sqlite3.connect('supermarket.db')
                    cursor = db_conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS suppliers (
                            supplier_id TEXT PRIMARY KEY,
                            supplier_name TEXT,
                            contact_number TEXT,
                            email TEXT
                        )
                    ''')
                    for sup in sample_suppliers:
                        cursor.execute("""
                            INSERT OR IGNORE INTO suppliers (supplier_id, supplier_name, contact_number, email)
                            VALUES (?, ?, ?, ?)
                        """, (sup['supplier_id'], sup['supplier_name'], sup['contact_number'], sup['email']))
                    db_conn.commit()
                    db_conn.close()
                st.success("✅ Sample suppliers added!")
                st.rerun()
            except Exception as e:
                st.error(f"Error adding suppliers: {e}")

        if products.empty:
            st.info("📦 Adding sample products...")

            sample_products = [
                {"product_code": "P001", "product_name": "Fresh Milk 1L", "category": "Dairy", "unit_price": 150.00, "is_ai_supported": False, "package_size": 1.00, "unit_of_measure": "L"},
                {"product_code": "P002", "product_name": "White Bread", "category": "Bakery", "unit_price": 200.00, "is_ai_supported": False, "package_size": 1.00, "unit_of_measure": "loaf"},
                {"product_code": "P004", "product_name": "Rice 5kg", "category": "Groceries", "unit_price": 800.00, "is_ai_supported": False, "package_size": 5.00, "unit_of_measure": "kg"},
                {"product_code": "SUG002", "product_name": "White Sugar 500g", "category": "Sugar", "unit_price": 115.00, "is_ai_supported": True, "package_size": 0.50, "unit_of_measure": "kg"},
                {"product_code": "SUG003", "product_name": "Brown Sugar 750g", "category": "Sugar", "unit_price": 285.00, "is_ai_supported": True, "package_size": 0.75, "unit_of_measure": "kg"},
            ]

            try:
                if conn_type == "supabase":
                    for prod in sample_products:
                        existing = conn.table("product_catalog").select("*").eq("product_code", prod["product_code"]).execute()
                        if not existing.data:
                            conn.table("product_catalog").insert(prod).execute()
                else:
                    db_conn = sqlite3.connect('supermarket.db')
                    cursor = db_conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS product_catalog (
                            product_code TEXT PRIMARY KEY,
                            product_name TEXT,
                            category TEXT,
                            unit_price REAL,
                            is_ai_supported BOOLEAN,
                            package_size REAL,
                            unit_of_measure TEXT
                        )
                    ''')
                    for prod in sample_products:
                        cursor.execute("""
                            INSERT OR IGNORE INTO product_catalog
                            (product_code, product_name, category, unit_price, is_ai_supported, package_size, unit_of_measure)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (prod['product_code'], prod['product_name'], prod['category'],
                              prod['unit_price'], prod['is_ai_supported'], prod['package_size'], prod['unit_of_measure']))
                    db_conn.commit()
                    db_conn.close()
                st.success("✅ Sample products added!")
                st.rerun()
            except Exception as e:
                st.error(f"Error adding products: {e}")

        # Check if deliveries exist
        if conn_type == "supabase":
            deliveries_check = conn.table("deliveries").select("*").limit(1).execute()
            if not deliveries_check.data:
                st.info("📝 No deliveries yet. Use 'Record Delivery' tab to add deliveries.")
        else:
            try:
                db_conn = sqlite3.connect('supermarket.db')
                cursor = db_conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM deliveries")
                count = cursor.fetchone()[0]
                db_conn.close()
                if count == 0:
                    st.info("📝 No deliveries yet. Use 'Record Delivery' tab to add deliveries.")
            except:
                pass

        return True

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

    # Call ensure_sample_data to check/initialize if needed
    ensure_sample_data()

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
           
            # =========================================================
            # SECTION 4: QUICK STATS (New)
            # =========================================================
            st.markdown("---")
            st.markdown("### 📊 Quick Statistics")
            
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            
            with col_stat1:
                # Top Performing Supplier
                top_supplier = df.groupby('supplier_name')['status'].apply(
                    lambda x: (x == '✅ Accurate').mean() * 100
                ).sort_values(ascending=False).head(1)
                if not top_supplier.empty:
                    st.metric("🏆 Top Supplier", top_supplier.index[0], 
                             f"{top_supplier.values[0]:.0f}% accuracy")
            
            with col_stat2:
                # Worst Performing Supplier
                worst_supplier = df.groupby('supplier_name')['status'].apply(
                    lambda x: (x == '⚠️ Short Shipped').mean() * 100
                ).sort_values(ascending=False).head(1)
                if not worst_supplier.empty:
                    st.metric("⚠️ Needs Attention", worst_supplier.index[0], 
                             f"{worst_supplier.values[0]:.0f}% short rate",
                             delta_color="inverse")
            
            with col_stat3:
                # Total Loss
                total_loss = abs(df[df['financial_impact'] < 0]['financial_impact'].sum())
                st.metric("💰 Total Loss", f"LKR {total_loss:,.2f}")
            
            with col_stat4:
                # Total Credit from Over-deliveries
                total_credit = df[df['financial_impact'] > 0]['financial_impact'].sum()
                st.metric("📦 Total Credit", f"LKR {total_credit:,.2f}")
            
            # =========================================================
            # SECTION 3: RECENT DELIVERIES TABLE (Enhanced)
            # =========================================================
            st.markdown("### 📋 Recent Deliveries")
            
            # Add filter options
            col_filter1, col_filter2, col_filter3 = st.columns(3)
            with col_filter1:
                show_limit = st.selectbox("Show rows", [10, 20, 50], index=0, key="dash_limit")
            with col_filter2:
                filter_status = st.selectbox("Filter by Status", ["All", "✅ Accurate", "⚠️ Short Shipped", "📦 Over Delivered"], key="dash_status")
            with col_filter3:
                suppliers_list = df['supplier_name'].unique().tolist()
                filter_supplier = st.selectbox("Filter by Supplier", ["All"] + suppliers_list, key="dash_supplier")
            
            # Apply filters
            filtered_df = df.copy()
            if filter_status != "All":
                filtered_df = filtered_df[filtered_df['status'] == filter_status]
            if filter_supplier != "All":
                filtered_df = filtered_df[filtered_df['supplier_name'] == filter_supplier]
            
            # Display table
            display_cols = ['delivery_date', 'invoice_number', 'supplier_name', 'product_name', 
                           'ordered_quantity', 'received_quantity', 'discrepancy_quantity', 
                           'discrepancy_percentage', 'financial_impact', 'status']
            
            if all(col in filtered_df.columns for col in display_cols):
                display_df = filtered_df[display_cols].head(show_limit).copy()
                display_df.columns = ['Date', 'Invoice #', 'Supplier', 'Product', 
                                     'Ordered', 'Received', 'Variance', 'Variance %', 
                                     'Financial Impact', 'Status']
                
                # Format numbers
                display_df['Ordered'] = display_df['Ordered'].apply(lambda x: f"{x:,.0f}")
                display_df['Received'] = display_df['Received'].apply(lambda x: f"{x:,.0f}")
                display_df['Variance'] = display_df['Variance'].apply(lambda x: f"{x:+,.0f}")
                display_df['Variance %'] = display_df['Variance %'].apply(lambda x: f"{x:+.1f}%")
                display_df['Financial Impact'] = display_df['Financial Impact'].apply(lambda x: f"LKR {x:+,.2f}")
                
                # Color code rows
                def color_status_rows(row):
                    if '⚠️ Short Shipped' in row['Status']:
                        return ['background-color: #ffcccc'] * len(row)
                    elif '📦 Over Delivered' in row['Status']:
                        return ['background-color: #ccffcc'] * len(row)
                    return [''] * len(row)
                
                st.dataframe(
                    display_df.style.apply(color_status_rows, axis=1),
                    use_container_width=True,
                    height=400
                )
            else:
                st.dataframe(filtered_df.head(show_limit), use_container_width=True)
            
                        # =========================================================
            # SECTION 5: ALERTS (Enhanced with Tooltips)
            # =========================================================
            st.markdown("---")
            st.markdown("### 🚨 Alerts")
            st.caption("ℹ️ **Hover over any alert** to see why it was triggered")
            
            alerts = []
            alert_explanations = []
            
            # Check for critical issues (loss > LKR 10,000)
            critical_loss = df[df['financial_impact'] < -10000]
            if not critical_loss.empty:
                for _, row in critical_loss.iterrows():
                    loss_amount = abs(row['financial_impact'])
                    alerts.append(f"🔴 CRITICAL: {row['supplier_name']} caused LKR {loss_amount:,.0f} loss on {row['product_name']}")
                    alert_explanations.append(f"""
                    **Why this alert?**
                    - Loss amount: LKR {loss_amount:,.0f}
                    - Threshold: > LKR 10,000
                    - Impact: This supplier has caused significant financial loss
                    - Recommended action: Immediate investigation required
                    """)
            
            # Check for repeat offenders (3+ short shipments)
            repeat_offenders = df[df['status'] == '⚠️ Short Shipped'].groupby('supplier_name').size()
            repeat_offenders = repeat_offenders[repeat_offenders >= 3]
            if not repeat_offenders.empty:
                for supplier, count in repeat_offenders.items():
                    alerts.append(f"⚠️ WARNING: {supplier} has {count} short shipments")
                    alert_explanations.append(f"""
                    **Why this alert?**
                    - Short shipments: {count}
                    - Threshold: 3 or more short shipments
                    - Pattern: This supplier consistently delivers less than ordered
                    - Recommended action: Schedule performance review meeting
                    """)
            
            # Check for improving trends
            supplier_trend = df.groupby('supplier_name').apply(
                lambda x: x['discrepancy_percentage'].mean() if len(x) >= 2 else 0
            )
            improving = supplier_trend[supplier_trend > 0].head(2)
            if not improving.empty:
                for supplier, trend in improving.items():
                    alerts.append(f"📈 IMPROVING: {supplier} shows {trend:.1f}% improvement")
                    alert_explanations.append(f"""
                    **Why this alert?**
                    - Improvement rate: {trend:.1f}%
                    - Positive trend: Discrepancy percentage is decreasing
                    - Impact: Supplier is getting better at accurate deliveries
                    - Recommended action: Acknowledge and encourage continued improvement
                    """)
            
            # Check for delivery accuracy drops (new)
            accuracy_drop = df.groupby('supplier_name').apply(
                lambda x: x['discrepancy_percentage'].mean() - x['discrepancy_percentage'].mean() if len(x) >= 2 else 0
            )
            # Check for products with high discrepancy rate
            product_issues = df[abs(df['discrepancy_percentage']) > 15].groupby('product_name').size()
            product_issues = product_issues[product_issues >= 2]
            if not product_issues.empty:
                for product, count in product_issues.items():
                    alerts.append(f"⚠️ PRODUCT ISSUE: {product} has {count} deliveries with >15% discrepancy")
                    alert_explanations.append(f"""
                    **Why this alert?**
                    - Product: {product}
                    - Problematic deliveries: {count}
                    - Threshold: >15% discrepancy
                    - Recommended action: Check quality control for this product
                    """)
            
            # Display alerts with hover explanations
            if alerts:
                for i, alert in enumerate(alerts[:5]):  # Show top 5 alerts
                    if "CRITICAL" in alert:
                        with st.expander(f"{alert}", expanded=False):
                            st.markdown(alert_explanations[i] if i < len(alert_explanations) else "**Investigate immediately**")
                    elif "WARNING" in alert or "PRODUCT ISSUE" in alert:
                        with st.expander(f"{alert}", expanded=False):
                            st.markdown(alert_explanations[i] if i < len(alert_explanations) else "**Needs attention**")
                    else:
                        with st.expander(f"{alert}", expanded=False):
                            st.markdown(alert_explanations[i] if i < len(alert_explanations) else "**Positive development**")
                
                if len(alerts) > 5:
                    st.caption(f"... and {len(alerts) - 5} more alerts")
            else:
                st.success("✅ No active alerts. All suppliers performing well!")
            
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
    # TAB 2: RECORD DELIVERY (continued)
    # =========================================================
    with tab2:
        st.markdown('<div class="section-title">📦 Record New Delivery</div>', unsafe_allow_html=True)

        

        # =========================================================
        # ADD THIS SECTION - View Recent Deliveries Table
        # =========================================================
        st.markdown("---")
        st.markdown("## 📋 Recent Deliveries")
        
        # Fetch recent deliveries to display
        if conn_type == "supabase":
            try:
                # Get recent deliveries with supplier and product info
                recent_response = conn.table("deliveries")\
                    .select("""
                        delivery_id,
                        invoice_number,
                        delivery_date,
                        suppliers(supplier_name),
                        delivery_items(
                            product_code,
                            billed_quantity,
                            received_quantity,
                            product_catalog(product_name)
                        )
                    """)\
                    .order("delivery_date", desc=True)\
                    .limit(20)\
                    .execute()
                
                recent_data = []
                for delivery in recent_response.data:
                    supplier_name = delivery.get('suppliers', {}).get('supplier_name', 'Unknown') if delivery.get('suppliers') else 'Unknown'
                    
                    for item in delivery.get('delivery_items', []):
                        product_info = item.get('product_catalog', {})
                        billed = float(item.get('billed_quantity', 0))
                        received = float(item.get('received_quantity', 0))
                        disc = received - billed
                        
                        recent_data.append({
                            'Date': delivery.get('delivery_date'),
                            'Invoice #': delivery.get('invoice_number'),
                            'Supplier': supplier_name,
                            'Product': product_info.get('product_name', 'Unknown'),
                            'Ordered': f"{billed:,.0f}",
                            'Received': f"{received:,.0f}",
                            'Variance': f"{disc:+,.0f}",
                            'Status': '⚠️ Short' if disc < 0 else '📦 Over' if disc > 0 else '✅ OK'
                        })
                
                if recent_data:
                    recent_df = pd.DataFrame(recent_data)
                    st.dataframe(recent_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No deliveries recorded yet.")
                    
            except Exception as e:
                st.info(f"Unable to load recent deliveries: {e}")
                
        else:
            # SQLite version
            try:
                db_conn = sqlite3.connect('supermarket.db')
                query = """
                    SELECT 
                        d.delivery_date as Date,
                        d.order_number as 'Invoice #',
                        s.supplier_name as Supplier,
                        p.product_name as Product,
                        d.ordered_quantity as Ordered,
                        d.received_quantity as Received,
                        d.discrepancy_quantity as Variance,
                        CASE 
                            WHEN d.discrepancy_quantity < 0 THEN '⚠️ Short '
                            WHEN d.discrepancy_quantity > 0 THEN '📦 Over'
                            ELSE '✅ OK'
                        END as Status
                    FROM deliveries d
                    LEFT JOIN suppliers s ON d.supplier_id = s.supplier_id
                    LEFT JOIN product_catalog p ON d.product_code = p.product_code
                    ORDER BY d.delivery_date DESC
                    LIMIT 20
                """
                recent_df = pd.read_sql_query(query, db_conn)
                db_conn.close()
                
                if not recent_df.empty:
                    st.dataframe(recent_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No deliveries recorded yet.")
                    
            except Exception as e:
                st.info(f"Unable to load recent deliveries: {e}")

            # =========================================================
    # FUNCTION: Calculate compensation for next order
    # =========================================================
    def calculate_next_order_adjustment(supplier_data):
        """Calculate how to adjust next order to compensate"""

        if supplier_data.empty:
            return None

        # Group by supplier and product to calculate cumulative shortages
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
                    'supplier': row['supplier'],  # ADDED supplier column
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
                    'supplier': row['supplier'],  # ADDED supplier column
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
                    'supplier': row['supplier'],  # ADDED supplier column
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
    # TAB 3: ORDER RECONCILIATION (Clean - Only Adjustments)
    # =========================================================
    with tab3:
        st.markdown('<div class="section-title">📦 Next Order Adjustments</div>', unsafe_allow_html=True)
        st.markdown("Automatically calculate what to add or credit in your next purchase order")
        
        # =========================================================
        # Date Range Selector with Validation
        # =========================================================
        col1, col2 = st.columns(2)
        
        today_date = date.today()
        
        with col1:
            rec_start_date = st.date_input(
                "📅 From Date", 
                value=today_date - timedelta(days=90), 
                key="rec_start",
                max_value=today_date
            )
        
        with col2:
            rec_end_date = st.date_input(
                "📅 To Date", 
                value=today_date, 
                key="rec_end",
                max_value=today_date
            )
        
        # Date Validation
        date_error = None
        if rec_start_date > rec_end_date:
            date_error = "❌ Start date cannot be after end date"
        elif rec_end_date > today_date:
            date_error = "❌ End date cannot be in the future"
        elif rec_start_date > today_date:
            date_error = "❌ Start date cannot be in the future"
        
        if date_error:
            st.error(date_error)
            st.stop()
        
        # =========================================================
        # Load data with validated dates
        # =========================================================
        rec_df = get_delivery_data_for_reconciliation(rec_start_date, rec_end_date)
        
        if rec_df.empty:
            st.warning("⚠️ No delivery data found for the selected period.")
            st.info("📝 Please record deliveries first in the 'Record Delivery' tab.")
        else:
            # =========================================================
            # Show Filter Only (Single instance - FIXED)
            # =========================================================
            show_only = st.selectbox(
                "🔍 Show",
                ["All Adjustments", "Only Shortages", "Only Credits", "No Adjustment Needed"],
                key="rec_show_filter"
            )
            
            # Calculate adjustments for ALL suppliers
            adjustments_df = calculate_next_order_adjustment(rec_df)
            
            if adjustments_df is None or adjustments_df.empty:
                st.info("No adjustments needed")
            else:
                # Apply show filter
                if show_only == "Only Shortages":
                    adjustments_df = adjustments_df[adjustments_df['cumulative_shortage'] > 0]
                elif show_only == "Only Credits":
                    adjustments_df = adjustments_df[adjustments_df['cumulative_overage'] > 0]
                elif show_only == "No Adjustment Needed":
                    adjustments_df = adjustments_df[adjustments_df['adjustment_qty'] == 0]
                
                if adjustments_df.empty:
                    st.info(f"No {show_only.lower()} found")
                else:
                    # =========================================================
                    # ADJUSTMENTS TABLE
                    # =========================================================
                    st.markdown("## 📋 Recommended Adjustments for Next Order")
                    
                    # Prepare display table
                    display_adjustments = adjustments_df[[
                        'supplier', 'product', 'cumulative_shortage', 'cumulative_overage', 
                        'net_position', 'adjustment_type', 'action', 'reason'
                    ]].copy()
                    
                    display_adjustments.columns = [
                        'Supplier', 'Product', 'Shortage (units)', 'Credit (units)', 
                        'Net Position', 'Type', 'Action', 'Reason'
                    ]
                    
                    # Color code rows
                    def color_adjustment_rows(row):
                        if 'Add to Next Order' in row['Type']:
                            return ['background-color: #ffcccc'] * len(row)
                        elif 'Credit' in row['Type']:
                            return ['background-color: #ccffcc'] * len(row)
                        return [''] * len(row)
                    
                    st.dataframe(
                        display_adjustments.style.apply(color_adjustment_rows, axis=1),
                        use_container_width=True,
                        height=400
                    )
                    
                    # =========================================================
                    # VISUAL SUMMARY (Charts Only)
                    # =========================================================
                    st.markdown("---")
                    st.markdown("## 📊 Adjustment Summary")
                    
                    col_chart1, col_chart2 = st.columns(2)
                    
                    with col_chart1:
                        # Bar chart - Top adjustments by product
                        chart_data = adjustments_df[adjustments_df['adjustment_qty'] > 0].copy()
                        if not chart_data.empty:
                            chart_data = chart_data.sort_values('adjustment_qty', ascending=True).tail(10)
                            fig = px.bar(
                                chart_data,
                                x='adjustment_qty',
                                y='product',
                                orientation='h',
                                color='adjustment_type',
                                title='Top Products Needing Adjustment',
                                labels={'adjustment_qty': 'Units to Adjust', 'product': 'Product'},
                                color_discrete_map={
                                    'Add to Next Order': '#e74c3c',
                                    'Credit for Next Order': '#2ecc71'
                                }
                            )
                            fig.update_layout(height=400)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No products need adjustment")
                    
                    with col_chart2:
                        # Donut chart - Adjustment distribution
                        type_counts = adjustments_df['adjustment_type'].value_counts().reset_index()
                        type_counts.columns = ['Type', 'Count']
                        
                        fig = px.pie(
                            type_counts,
                            values='Count',
                            names='Type',
                            title='Adjustment Distribution',
                            hole=0.4,
                            color='Type',
                            color_discrete_map={
                                'Add to Next Order': '#e74c3c',
                                'Credit for Next Order': '#2ecc71',
                                'No Adjustment': '#95a5a6'
                            }
                        )
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # =========================================================
                    # SUMMARY BY SUPPLIER
                    # =========================================================
                    st.markdown("---")
                    st.markdown("## 🏭 Summary by Supplier")
                    
                    supplier_summary = adjustments_df.groupby('supplier').agg({
                        'cumulative_shortage': 'sum',
                        'cumulative_overage': 'sum',
                        'adjustment_qty': 'sum'
                    }).reset_index()
                    
                    supplier_summary['net'] = supplier_summary['cumulative_shortage'] - supplier_summary['cumulative_overage']
                    supplier_summary = supplier_summary.sort_values('net', ascending=False)
                    
                    for _, row in supplier_summary.iterrows():
                        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                        with col1:
                            st.write(f"**{row['supplier']}**")
                        with col2:
                            if row['cumulative_shortage'] > 0:
                                st.write(f"📦 Short: {row['cumulative_shortage']:,.0f} units")
                        with col3:
                            if row['cumulative_overage'] > 0:
                                st.write(f"💰 Credit: {row['cumulative_overage']:,.0f} units")
                        with col4:
                            if row['net'] > 0:
                                st.warning(f"+{row['net']:,.0f} to add")
                            elif row['net'] < 0:
                                st.success(f"{row['net']:+,.0f} credit")
                            else:
                                st.success("✅ Balanced")
                    
                    # =========================================================
                    # ACTION BUTTONS
                    # =========================================================
                    st.markdown("---")
                    st.markdown("## 📤 Actions")
                    
                    total_shortage = adjustments_df['cumulative_shortage'].sum()
                    total_credit = adjustments_df['cumulative_overage'].sum()
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("📥 Export Adjustments to Excel", use_container_width=True, key="rec_export"):
                            with pd.ExcelWriter('next_order_adjustments.xlsx') as writer:
                                display_adjustments.to_excel(writer, sheet_name='Adjustments', index=False)
                            st.success("✅ Adjustments saved as 'next_order_adjustments.xlsx'")
                    
                    with col2:
                        if st.button("📋 Generate Purchase Order", use_container_width=True, key="rec_po"):
                            if total_shortage > 0:
                                st.success(f"✅ Purchase order generated with +{total_shortage:,.0f} extra units")
                                if total_credit > 0:
                                    st.info(f"💰 Credit of {total_credit:,.0f} units applied")
                            else:
                                st.success("✅ Purchase order generated with no adjustments")
                    
                    with col3:
                        if st.button("📧 Email Recommendations", use_container_width=True, key="rec_email"):
                            st.info("📧 Recommendations ready to email to procurement team")
=======
                            'product_name': product.get('product_name', 'Unknown'),
                            'category': product.get('category', 'Unknown'),
                            'cost_price': float(product.get('cost_price', 0)),
                            'ordered_quantity': float(item.get('billed_quantity', 0)),
                            'received_quantity': float(item.get('received_quantity', 0))
                        })
            
            df = pd.DataFrame(data)
            
            if not df.empty:
                df['discrepancy_quantity'] = df['received_quantity'] - df['ordered_quantity']
                df['discrepancy_percentage'] = (df['discrepancy_quantity'] / df['ordered_quantity'] * 100).round(1)
                df['financial_impact'] = df['discrepancy_quantity'] * df['cost_price']
        
        elif conn_type == "sqlite":
            query = """
                SELECT 
                    d.delivery_date,
                    d.invoice_number,
                    d.product_code,
                    p.product_name,
                    p.category,
                    p.cost_price,
                    d.ordered_quantity,
                    d.received_quantity,
                    d.discrepancy_quantity,
                    d.discrepancy_percentage,
                    d.financial_impact,
                    s.supplier_name
                FROM deliveries d
                LEFT JOIN products p ON d.product_code = p.product_code
                LEFT JOIN suppliers s ON d.supplier_id = s.supplier_id
                WHERE d.delivery_date IS NOT NULL
                ORDER BY d.delivery_date DESC
            """
            df = pd.read_sql_query(query, conn)
        
        else:
            df = pd.DataFrame()
            st.error("Unknown database connection type")
            
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        df = pd.DataFrame()
    
    # ============================================
    # CHECK IF DATA EXISTS
    # ============================================
    if df.empty:
        st.warning("No data available. Please add deliveries first.")
        st.stop()
    
    # Calculate status
    conditions = [
        abs(df['discrepancy_quantity']) < 0.01,
        df['discrepancy_quantity'] < 0,
        df['discrepancy_quantity'] > 0
    ]
    choices = [' Accurate', ' Short Shipped', ' Over Delivered']
    df['status'] = np.select(conditions, choices, default='Unknown')
    
    # ============================================
    # SIDEBAR FILTERS
    # ============================================
    st.sidebar.markdown("###  Filters")
    
    # Check if date column exists
    if 'delivery_date' in df.columns and not df.empty:
        min_date = pd.to_datetime(df['delivery_date']).min().date()
        max_date = pd.to_datetime(df['delivery_date']).max().date()
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("From", value=min_date)
        with col2:
            end_date = st.date_input("To", value=max_date)
        
        # Apply date filter
        filtered_df = df[
            (pd.to_datetime(df['delivery_date']).dt.date >= start_date) &
            (pd.to_datetime(df['delivery_date']).dt.date <= end_date)
        ]
    else:
        filtered_df = df.copy()
    
    # Category filter (if column exists)
    if 'category' in filtered_df.columns and not filtered_df.empty:
        categories = ['All'] + sorted(filtered_df['category'].dropna().unique().tolist())
        selected_category = st.sidebar.selectbox("Category", categories)
        if selected_category != 'All':
            filtered_df = filtered_df[filtered_df['category'] == selected_category]
    
    # Product filter (if column exists)
    if 'product_name' in filtered_df.columns and not filtered_df.empty:
        products = ['All'] + sorted(filtered_df['product_name'].dropna().unique().tolist())
        selected_product = st.sidebar.selectbox("Product", products)
        if selected_product != 'All':
            filtered_df = filtered_df[filtered_df['product_name'] == selected_product]
    
    # Supplier filter (if column exists)
    if 'supplier_name' in filtered_df.columns and not filtered_df.empty:
        suppliers = ['All'] + sorted(filtered_df['supplier_name'].dropna().unique().tolist())
        selected_supplier = st.sidebar.selectbox("Supplier", suppliers)
        if selected_supplier != 'All':
            filtered_df = filtered_df[filtered_df['supplier_name'] == selected_supplier]
    
    if filtered_df.empty:
        st.warning("No data matches your filters")
        st.stop()
    
    # ============================================
    # KPI METRICS
    # ============================================
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Products Analyzed", filtered_df['product_name'].nunique())
    with col2:
        st.metric("Total Deliveries", len(filtered_df))
    with col3:
        st.metric("Discrepancies", len(filtered_df[filtered_df['status'] != ' Accurate']))
    with col4:
        total_financial = filtered_df['financial_impact'].sum()
        st.metric("Financial Impact", f"LKR {abs(total_financial):,.2f}")
    
    # ============================================
    # PRODUCT RANKINGS TABS
    # ============================================
    st.markdown("###  Product Rankings")
    
    tab1, tab2, tab3, tab4 = st.tabs([" Highest Discrepancy", " Highest Financial Loss", "Most Frequent", " Most Accurate"])
    
    with tab1:
        product_rank = filtered_df.groupby('product_name')['discrepancy_percentage'].mean().reset_index()
        product_rank = product_rank.sort_values('discrepancy_percentage', ascending=False).head(10)
        if not product_rank.empty:
            st.dataframe(product_rank, width='stretch')
    
    with tab2:
        loss_rank = filtered_df.groupby('product_name')['financial_impact'].sum().reset_index()
        loss_rank = loss_rank.sort_values('financial_impact', ascending=True).head(10)
        if not loss_rank.empty:
            st.dataframe(loss_rank, width='stretch')
    
    with tab3:
        freq_rank = filtered_df.groupby('product_name').agg({
            'status': lambda x: (x != ' Accurate').count(),
            'delivery_date': 'count'
        }).reset_index()
        freq_rank.columns = ['Product', 'Issues', 'Total Deliveries']
        freq_rank['Issue Rate %'] = (freq_rank['Issues'] / freq_rank['Total Deliveries'] * 100).round(1)
        freq_rank = freq_rank.sort_values('Issues', ascending=False).head(10)
        if not freq_rank.empty:
            st.dataframe(freq_rank, width='stretch')
    
    with tab4:
        accurate_rank = filtered_df.groupby('product_name').agg({
            'status': lambda x: (x == ' Accurate').sum(),
            'delivery_date': 'count'
        }).reset_index()
        accurate_rank.columns = ['Product', 'Accurate', 'Total']
        accurate_rank['Accuracy %'] = (accurate_rank['Accurate'] / accurate_rank['Total'] * 100).round(1)
        accurate_rank = accurate_rank.sort_values('Accuracy %', ascending=False).head(10)
        if not accurate_rank.empty:
            st.dataframe(accurate_rank, width='stretch')
    
    # ============================================
    # DETAILED TABLE
    # ============================================
    st.markdown("###  Detailed Product Performance")
    
    summary_df = filtered_df.groupby(['product_name', 'category']).agg({
        'ordered_quantity': 'sum',
        'received_quantity': 'sum',
        'discrepancy_quantity': 'sum',
        'discrepancy_percentage': 'mean',
        'financial_impact': 'sum',
        'status': lambda x: (x != ' Accurate').sum(),
        'delivery_date': 'count'
    }).reset_index()
    
    summary_df.columns = ['Product', 'Category', 'Ordered', 'Received', 'Net Discrepancy', 
                          'Avg Disc %', 'Financial Impact', 'Issues', 'Deliveries']
    summary_df['Accuracy %'] = ((summary_df['Deliveries'] - summary_df['Issues']) / summary_df['Deliveries'] * 100).round(1)
    
    st.dataframe(summary_df.head(20), width='stretch')
    
    # Export button
    csv = summary_df.to_csv(index=False)
    st.download_button(
        label="Export Report",
        data=csv,
        file_name=f"product_performance_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

# Close SQLite connection if needed
if conn_type == "sqlite" and hasattr(conn, 'close'):
    conn.close()
>>>>>>> origin/main
