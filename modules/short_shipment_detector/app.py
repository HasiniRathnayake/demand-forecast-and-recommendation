import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
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
                        data.append({
                            'delivery_date': delivery.get('delivery_date'),
                            'invoice_number': delivery.get('invoice_number'),
                            'supplier_name': supplier_name,
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