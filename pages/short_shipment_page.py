# pages/short_shipment_page.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import numpy as np
import sqlite3
import sys
import os

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
            .in_("status", ["SENT", "PENDING_DISPATCH"])\
            .execute()
        
        if not po_response.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(po_response.data)
        
        suppliers_response = conn.table("suppliers").select("supplier_id, supplier_name").execute()
        if suppliers_response.data:
            suppliers_df = pd.DataFrame(suppliers_response.data)
            df = df.merge(suppliers_df, left_on='supplier_id', right_on='supplier_id', how='left')
            df['supplier_name'] = df['supplier_name'].fillna('Unknown')
        
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
    """Wrapper that renders short shipment module inside shared app"""

    from modules.short_shipment_detector.database import (
        get_db_connection, init_database,
        get_suppliers_sqlite, get_products_sqlite
    )
    
    init_database()
    init_delivery_draft_table()
    detector = ShortShipmentDetector()
    
    conn = get_db_connection()
    conn_type = "supabase" if hasattr(conn, 'table') else "sqlite"
    
    # =========================================================
    # PAGE STYLING
    # =========================================================
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
            margin-bottom: 2rem;
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
        .success-message {
            background-color: #d4edda;
            color: #155724;
            padding: 10px;
            border-radius: 8px;
            border-left: 4px solid #28a745;
            margin: 10px 0;
        }
        .info-message {
            background-color: #d1ecf1;
            color: #0c5460;
            padding: 10px;
            border-radius: 8px;
            border-left: 4px solid #17a2b8;
            margin: 10px 0;
        }
        .footer {
            text-align: center;
            padding: 15px;
            margin-top: 20px;
            color: #6c757d;
            font-size: 0.75rem;
            border-top: 1px solid #dee2e6;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="main-title">📦 Short Shipment Detection System</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Track discrepancies between ordered and received quantities</div>', unsafe_allow_html=True)
    
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

    # =========================================================
    # Function to get pending purchase orders
    # =========================================================
    def get_pending_purchase_orders():
        """Fetch purchase orders waiting to be delivered (from Replenishment system)"""
        try:
            if conn_type == "supabase":
                response = conn.table("purchase_orders")\
                    .select("po_id, status, replenishment_orders(product_code, suggested_qty), suppliers(supplier_name)")\
                    .eq("status", "SENT").execute()
                
                data = []
                for po in response.data:
                    rep = po.get('replenishment_orders') or {}
                    sup = po.get('suppliers') or {}
                    data.append({
                        "po_id": po.get('po_id'),
                        "supplier_name": sup.get('supplier_name', 'Unknown'),
                        "product_code": rep.get('product_code', 'Unknown'),
                        "ordered_qty": rep.get('suggested_qty', 0)
                    })
                return pd.DataFrame(data)
            else:
                return pd.DataFrame()
        except Exception as e:
            st.error(f"Error fetching pending POs: {e}")
            return pd.DataFrame()

    # =========================================================
    # Draft storage for Record Delivery (persistent across restarts)
    # =========================================================
    def init_delivery_draft_table():
        """Create draft table in local SQLite for persistent form drafts."""
        db_conn = sqlite3.connect('supermarket.db')
        cursor = db_conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delivery_drafts (
                draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL,
                supplier_name TEXT NOT NULL,
                product_name TEXT NOT NULL,
                ordered_quantity REAL NOT NULL,
                received_quantity REAL NOT NULL,
                discrepancy_quantity REAL NOT NULL,
                discrepancy_percentage REAL NOT NULL,
                delivery_date TEXT NOT NULL,
                source_type TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db_conn.commit()
        db_conn.close()

    def save_delivery_draft(order_number, supplier_name, product_name, ordered_qty, received_qty, delivery_date, source_type):
        """Persist one draft row to local SQLite."""
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

    def get_delivery_drafts(limit=50):
        """Load recent drafts from local SQLite."""
        db_conn = sqlite3.connect('supermarket.db')
        query = """
            SELECT
                draft_id,
                created_at,
                order_number,
                supplier_name,
                product_name,
                ordered_quantity,
                received_quantity,
                discrepancy_quantity,
                discrepancy_percentage,
                delivery_date,
                source_type
            FROM delivery_drafts
            ORDER BY draft_id DESC
            LIMIT ?
        """
        drafts_df = pd.read_sql_query(query, db_conn, params=[limit])
        db_conn.close()
        return drafts_df

    def get_delivery_drafts_for_reconciliation(start_date, end_date):
        """Load draft deliveries for a date range and map them to reconciliation schema."""
        db_conn = sqlite3.connect('supermarket.db')
        query = """
            SELECT
                d.draft_id,
                d.delivery_date as date,
                d.order_number as invoice,
                d.supplier_name as supplier,
                d.product_name as product,
                COALESCE(p.product_code, 'DRAFT') as product_code,
                d.ordered_quantity as ordered,
                d.received_quantity as received,
                d.discrepancy_quantity as discrepancy_qty,
                d.discrepancy_percentage as discrepancy_pct,
                COALESCE(p.unit_price, 0) as unit_price
            FROM delivery_drafts d
            LEFT JOIN product_catalog p ON d.product_name = p.product_name
            WHERE date(d.delivery_date) BETWEEN date(?) AND date(?)
            ORDER BY date(d.delivery_date) DESC, d.draft_id DESC
        """
        drafts_df = pd.read_sql_query(
            query,
            db_conn,
            params=[start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')],
        )
        db_conn.close()

        if drafts_df.empty:
            return drafts_df

        drafts_df['financial_impact'] = drafts_df['discrepancy_qty'] * drafts_df['unit_price']
        drafts_df['status'] = drafts_df['discrepancy_qty'].apply(
            lambda x: 'Short' if x < 0 else 'Over' if x > 0 else 'Accurate'
        )
        drafts_df['source'] = 'Draft'
        drafts_df['delivery_id'] = drafts_df['draft_id'].apply(lambda x: f"DRAFT-{x}")
        return drafts_df

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
                            'status': 'Short' if disc_qty < 0 else 'Over' if disc_qty > 0 else 'Accurate',
                            'source': 'Finalized'
                        })

                df = pd.DataFrame(data)
                if not df.empty:
                    df['source'] = 'Finalized'
                    return df

                # Fallback: show local saved drafts when finalized records are unavailable
                return get_delivery_drafts_for_reconciliation(start_date, end_date)
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
                    df['source'] = 'Finalized'
                    return df

                # Fallback: show local saved drafts when finalized records are unavailable
                return get_delivery_drafts_for_reconciliation(start_date, end_date)
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
    init_delivery_draft_table()

    # =========================================================
    # Navigation Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📦 Record Delivery", "🏆 Order Reconciliation"])
    
    # =========================================================
    # TAB 1: DASHBOARD
    # =========================================================
    with tab1:
        st.markdown('<div class="section-header">📊 Shipment Dashboard</div>', unsafe_allow_html=True)
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            start_date = st.date_input("📅 From Date", value=date.today() - timedelta(days=30), key="dashboard_start_date")
        with col_d2:
            end_date = st.date_input("To", value=date.today(), key="dash_end")

        is_valid, errors = validate_dates(start_date, end_date)
        if not is_valid:
            for error in errors:
                st.warning(error)
            df = pd.DataFrame()
            dashboard_source = "None"
        else:
            df = get_deliveries(start_date, end_date)
            dashboard_source = "Finalized"

            if df.empty:
                drafts_df = get_delivery_drafts_for_reconciliation(start_date, end_date)
                if not drafts_df.empty:
                    status_map = {
                        'Accurate': '✅ Accurate',
                        'Short': '⚠️ Short Shipped',
                        'Over': '📦 Over Delivered',
                    }
                    df = pd.DataFrame({
                        'delivery_date': drafts_df['date'],
                        'invoice_number': drafts_df['invoice'],
                        'supplier_name': drafts_df['supplier'],
                        'product_name': drafts_df['product'],
                        'ordered_quantity': drafts_df['ordered'],
                        'received_quantity': drafts_df['received'],
                        'discrepancy_quantity': drafts_df['discrepancy_qty'],
                        'discrepancy_percentage': drafts_df['discrepancy_pct'],
                        'financial_impact': drafts_df['financial_impact'],
                        'status': drafts_df['status'].map(status_map).fillna('Unknown'),
                    })
                    dashboard_source = "Draft"

        df = get_deliveries(start_date, end_date)
        
        if df.empty:
            st.info("📭 No deliveries found in the selected date range.")
        else:
            if dashboard_source == "Draft":
                st.warning("Showing dashboard from saved drafts because no finalized deliveries were found in this period.")
            st.caption(f"Dashboard source: {dashboard_source} | Rows: {len(df)}")

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

        st.markdown("---")
        st.markdown("## 🚨 Alerts")
        st.caption("ℹ️ Hover over any alert to see why it was triggered")

        if df.empty:
            st.info("No alert data available for the selected date range.")
        else:
            alerts = []

            short_df = df[df['discrepancy_quantity'] < 0].copy()
            if not short_df.empty:
                short_df['loss_lkr'] = short_df['financial_impact'].abs()
                loss_by_supplier_product = (
                    short_df.groupby(['supplier_name', 'product_name'], dropna=False)['loss_lkr']
                    .sum()
                    .reset_index()
                    .sort_values('loss_lkr', ascending=False)
                )

                for _, row in loss_by_supplier_product.head(3).iterrows():
                    loss_val = float(row['loss_lkr'])
                    if loss_val >= 20000:
                        level = "🔴 CRITICAL"
                    elif loss_val >= 10000:
                        level = "🟠 HIGH"
                    else:
                        level = "🟡 WATCH"

                    alerts.append({
                        'title': (
                            f"{level}: {row['supplier_name']} caused LKR {loss_val:,.0f} "
                            f"loss on {row['product_name']}"
                        ),
                        'details': (
                            f"Total shortage loss for this supplier-product combination in the selected period: "
                            f"LKR {loss_val:,.2f}."
                        ),
                    })

            trend_df = df.copy()
            trend_df['delivery_date'] = pd.to_datetime(trend_df['delivery_date'], errors='coerce')
            trend_df = trend_df.dropna(subset=['delivery_date'])
            if not trend_df.empty:
                trend_df = trend_df.sort_values('delivery_date')
                for supplier_name, supplier_rows in trend_df.groupby('supplier_name'):
                    if len(supplier_rows) < 4:
                        continue

                    midpoint = len(supplier_rows) // 2
                    earlier = supplier_rows.iloc[:midpoint]
                    recent = supplier_rows.iloc[midpoint:]

                    earlier_abs = earlier['discrepancy_percentage'].abs().mean()
                    recent_abs = recent['discrepancy_percentage'].abs().mean()
                    if earlier_abs <= 0:
                        continue

                    improvement_pct = ((earlier_abs - recent_abs) / earlier_abs) * 100
                    if improvement_pct >= 3:
                        alerts.append({
                            'title': f"📈 IMPROVING: {supplier_name} shows {improvement_pct:.1f}% improvement",
                            'details': (
                                f"Average absolute discrepancy improved from {earlier_abs:.1f}% "
                                f"to {recent_abs:.1f}% across the selected deliveries."
                            ),
                        })

            if not alerts:
                st.success("✅ No critical issues detected for the selected period.")
            else:
                for alert in alerts[:6]:
                    with st.expander(alert['title']):
                        st.write(alert['details'])

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

            bcol1, bcol2 = st.columns(2)
            save_delivery_clicked = bcol1.button("💾 Save Delivery", type="primary", use_container_width=True)
            save_draft_clicked = bcol2.button("📝 Save Draft", use_container_width=True)

            if save_draft_clicked:
                if not order_num:
                    st.error("Please enter an order number before saving draft.")
                elif ordered_qty == 0:
                    st.error("Ordered quantity cannot be zero.")
                else:
                    source_type = "auto_po" if is_auto else "manual"
                    try:
                        save_delivery_draft(
                            order_number=order_num,
                            supplier_name=supplier,
                            product_name=product,
                            ordered_qty=ordered_qty,
                            received_qty=received_qty,
                            delivery_date=del_date.strftime('%Y-%m-%d'),
                            source_type=source_type,
                        )
                        st.success("✅ Draft saved. It will remain available after app restart.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving draft: {e}")

            if save_delivery_clicked:
                if not order_num:
                    st.error("Please enter an order number.")
                elif ordered_qty == 0:
                    st.error("Ordered quantity cannot be zero.")
                else:
                    try:
                        selected_product = products_df[products_df['product_name'] == product].iloc[0]
                        product_code = selected_product['product_code']
                        unit_price = selected_product.get('unit_price', 0)
                        disc_qty = received_qty - ordered_qty
                        financial_impact = disc_qty * unit_price
                        
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

                                # --- START PO HANDSHAKE ---
                                if is_auto:
                                    conn.table("purchase_orders").update({"status": "DELIVERED"}).eq("po_id", auto_po['po_id']).execute()
                                # --- END PO HANDSHAKE ---

                            st.success("✅ Delivery recorded successfully!")
                            st.balloons()
                            
                            # Clear session state
                            for key in ['auto_supplier', 'auto_product', 'auto_ordered_qty', 'selected_po_id']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error saving delivery: {e}")
                            # =========================================================
    # FUNCTION: Calculate compensation for next order (UPDATED)
    # =========================================================
    def calculate_next_order_adjustment(supplier_data):
        """Calculate how to adjust next order to compensate - INCLUDES ALL SUPPLIERS"""
        
        if supplier_data.empty:
            return None

        # Group by supplier AND product to calculate cumulative shortages
        product_summary = supplier_data.groupby(['supplier', 'product_code', 'product']).agg({
            'ordered': 'sum',
            'received': 'sum',
            'discrepancy_qty': 'sum',
            'financial_impact': 'sum',
            'unit_price': 'first'
        }).reset_index()

            st.markdown("---")
            st.markdown("#### 🗂️ Saved Delivery Drafts")
            drafts_df = get_delivery_drafts(limit=50)
            if drafts_df.empty:
                st.info("No saved drafts yet. Click 'Save Draft' to store ordered vs received shipment details.")
            else:
                view_df = drafts_df.copy()
                view_df.columns = [
                    "Draft ID",
                    "Saved At",
                    "Order/Invoice",
                    "Supplier",
                    "Product",
                    "Ordered Qty",
                    "Received Qty",
                    "Variance Qty",
                    "Variance %",
                    "Delivery Date",
                    "Source",
                ]
                st.dataframe(view_df, use_container_width=True, hide_index=True)

    # =========================================================
    # TAB 2: RECORD DELIVERY (continued)
    # =========================================================
    with tab3:
        st.markdown('<div class="section-title">📊 Order vs Received Reconciliation</div>', unsafe_allow_html=True)
        st.markdown("Track discrepancies and automatically adjust future orders")

        recon_columns = [
            'Date',
            'Order/Invoice',
            'Supplier',
            'Product Code',
            'Product',
            'Ordered Qty',
            'Received Qty',
            'Variance Qty',
            'Variance %',
            'Financial Impact (LKR)',
            'Status',
            'Source',
        ]

        # Date Range Selector
        col1, col2 = st.columns(2)
        with col1:
            rec_start_date = st.date_input("From Date", value=date.today() - timedelta(days=365), key="rec_start")
        with col2:
            rec_end_date = st.date_input("To Date", value=date.today(), key="rec_end")

        # Load data
        rec_df = get_delivery_data_for_reconciliation(rec_start_date, rec_end_date)
        st.caption(f"Rows loaded for reconciliation: {len(rec_df)}")

        if not rec_df.empty and 'source' in rec_df.columns and (rec_df['source'] == 'Draft').all():
            st.warning("Showing draft rows because no finalized deliveries were found for this period.")

        if rec_df.empty:
            st.info("No delivery data found for the selected period. Try a wider date range or record at least one delivery in Tab 2.")
            st.markdown("## 📋 Reconciliation Table")
            st.dataframe(pd.DataFrame(columns=recon_columns), use_container_width=True, hide_index=True)
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
            # SECTION 2: ORDER RECONCILIATION TABLE
            # =========================================================
            st.markdown("## 📋 Reconciliation Table")

            suppliers_list = sorted(rec_df['supplier'].dropna().unique().tolist())

            f1, f2 = st.columns(2)
            with f1:
                selected_supplier = st.selectbox(
                    "Supplier Filter",
                    ["All Suppliers"] + suppliers_list,
                    key="recon_supplier_filter",
                )
            with f2:
                selected_status = st.selectbox(
                    "Status Filter",
                    ["All", "Short", "Over", "Accurate"],
                    key="recon_status_filter",
                )

            filtered_df = rec_df.copy()
            if selected_supplier != "All Suppliers":
                filtered_df = filtered_df[filtered_df['supplier'] == selected_supplier]
            if selected_status != "All":
                filtered_df = filtered_df[filtered_df['status'] == selected_status]

            if filtered_df.empty:
                st.info("No reconciliation rows match the selected filters.")
            else:
                recon_table = filtered_df[[
                    'date',
                    'invoice',
                    'supplier',
                    'product_code',
                    'product',
                    'ordered',
                    'received',
                    'discrepancy_qty',
                    'discrepancy_pct',
                    'financial_impact',
                    'status',
                    'source',
                ]].copy()

                recon_table['date'] = pd.to_datetime(recon_table['date'], errors='coerce').dt.strftime('%Y-%m-%d')
                recon_table['ordered'] = recon_table['ordered'].round(2)
                recon_table['received'] = recon_table['received'].round(2)
                recon_table['discrepancy_qty'] = recon_table['discrepancy_qty'].round(2)
                recon_table['discrepancy_pct'] = recon_table['discrepancy_pct'].round(1)
                recon_table['financial_impact'] = recon_table['financial_impact'].round(2)

                recon_table.columns = recon_columns

                st.dataframe(recon_table, use_container_width=True, hide_index=True)

            # =========================================================
            # SECTION 3: SUPPLIER RECONCILIATION
            # =========================================================
            st.markdown("## 🏭 Supplier Reconciliation")

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
        st.markdown('<div class="section-header">📊 Order Reconciliation</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            rec_start = st.date_input("📅 From Date", value=date.today() - timedelta(days=90), key="recon_start_date")
        with col2:
            rec_end = st.date_input("📅 To Date", value=date.today(), key="recon_end_date")
        
        rec_df = get_delivery_data_for_reconciliation(rec_start, rec_end)
        
        if rec_df.empty:
            st.info("📭 No delivery data found for the selected period.")
        else:
            show_only = st.selectbox(
                "🔍 Filter Adjustments",
                ["All Adjustments", "Only Shortages", "Only Credits", "No Adjustment Needed"],
                key="rec_show_filter"
            )
            
            adjustments_df = calculate_next_order_adjustment(rec_df)
            
            if adjustments_df is not None and not adjustments_df.empty:
                if show_only == "Only Shortages":
                    adjustments_df = adjustments_df[adjustments_df['cumulative_shortage'] > 0]
                elif show_only == "Only Credits":
                    adjustments_df = adjustments_df[adjustments_df['cumulative_overage'] > 0]
                elif show_only == "No Adjustment Needed":
                    adjustments_df = adjustments_df[adjustments_df['adjustment_qty'] == 0]
                
                if adjustments_df.empty:
                    st.info(f"📭 No {show_only.lower()} found")
                else:
                    st.markdown("### 📋 Recommended Adjustments for Next Order")
                    st.dataframe(adjustments_df[['supplier', 'product', 'adjustment_type', 'adjustment_qty', 'reason']], width='stretch')

# This is the END of render_short_shipment - NO CODE AFTER THIS!