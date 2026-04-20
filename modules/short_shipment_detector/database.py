import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ Supabase not installed. Using SQLite fallback.")

# ============================================
# CONNECTION VALIDATION
# ============================================

@st.cache_resource
def get_supabase_client():
    """
    Initialize and cache Supabase client with validation
    Returns: client or None if validation fails
    """
    if not SUPABASE_AVAILABLE:
        st.warning("⚠️ Supabase package not installed")
        return None
    
    try:
        # Validate secrets exist
        if not hasattr(st, 'secrets'):
            st.warning("⚠️ Streamlit secrets not found")
            return None
            
        if 'SUPABASE_URL' not in st.secrets:
            st.warning("⚠️ SUPABASE_URL not found in secrets")
            return None
            
        if 'SUPABASE_KEY' not in st.secrets:
            st.warning("⚠️ SUPABASE_KEY not found in secrets")
            return None
        
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        
        # Validate URL format
        if not url.startswith("https://"):
            st.warning("⚠️ Invalid Supabase URL - must start with https://")
            return None
        
        if not url.endswith(".supabase.co") and not "supabase" in url:
            st.warning("⚠️ Invalid Supabase URL format")
            return None
        
        # Attempt connection
        client = create_client(url, key)
        
        # Test connection with simple query
        test = client.table("suppliers").select("*").limit(1).execute()
        return client
        
    except Exception as e:
        st.warning(f"⚠️ Supabase connection failed: {e}")
        return None


def get_sqlite_connection():
    """
    Get SQLite connection with validation
    Returns: connection or None
    """
    try:
        conn = sqlite3.connect('supermarket.db')
        # Test connection
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        return conn
    except Exception as e:
        st.error(f" SQLite connection failed !!: {e}")
        return None


def get_db_connection():
    """
    Get database connection - Supabase first, then SQLite fallback
    Returns: connection object
    """
    # Try Supabase first
    supabase = get_supabase_client()
    if supabase:
        return supabase
    
    # Fallback to SQLite
    st.info(" Using SQLite database (offline mode)")
    sqlite_conn = get_sqlite_connection()
    if sqlite_conn:
        return sqlite_conn
    
    st.error(" No database connection available")
    return None


# ============================================
# DATABASE INITIALIZATION
# ============================================

def init_database():
    """Initialize SQLite tables with validation"""
    conn = get_sqlite_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Create suppliers table with validation constraints
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suppliers (
                supplier_id VARCHAR PRIMARY KEY,
                supplier_name TEXT NOT NULL,
                contact_person TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                payment_terms TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (supplier_id != ''),
                CHECK (supplier_name != '')
            )
        ''')
        
        # Create products table with validation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_code VARCHAR PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT,
                unit_price REAL CHECK (unit_price > 0),
                cost_price REAL CHECK (cost_price > 0),
                reorder_level INTEGER DEFAULT 10,
                CHECK (product_code != ''),
                CHECK (product_name != '')
            )
        ''')
        
        # Create deliveries table with validation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deliveries (
                delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL,
                supplier_id INTEGER,
                product_code TEXT,
                ordered_quantity INTEGER CHECK (ordered_quantity >= 0),
                received_quantity INTEGER CHECK (received_quantity >= 0),
                delivery_date DATE NOT NULL,
                discrepancy_quantity INTEGER,
                discrepancy_percentage REAL,
                financial_impact REAL,
                notes TEXT,
                FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id),
                FOREIGN KEY (product_code) REFERENCES products (product_code)
            )
        ''')
        
        conn.commit()
        print(" SQLite database initialized with validation")
        return True
        
    except Exception as e:
        print(f" SQLite initialization error: {e}")
        return False
    finally:
        conn.close()


# ============================================
# SAMPLE DATA WITH VALIDATION
# ============================================

def add_sample_data():
    """Add sample data to SQLite with validation"""
    conn = get_sqlite_connection()
    if not conn:
        st.error(" Cannot connect to database")
        return
    
    try:
        cursor = conn.cursor()
        
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM suppliers")
        if cursor.fetchone()[0] > 0:
            st.info(" Sample data already exists")
            return
        
        # Insert validated sample suppliers
        suppliers = [
            ('SUP001', 'Fresh Foods Ltd', 'John Smith', '555-0101', 'john@freshfoods.com', '123 Dairy St', 'Net 30'),
            ('SUP002', 'Bakery Express', 'Jane Doe', '555-0102', 'jane@bakery.com', '456 Flour Ave', 'Net 15'),
            ('SUP003', 'Global Grocers', 'Bob Wilson', '555-0103', 'bob@global.com', '789 Market Rd', 'Net 45')
        ]
        
        for s in suppliers:
            # Validate before insert
            if not s[0] or not s[1]:
                st.warning(f"⚠️ Skipping invalid supplier: {s}")
                continue
            cursor.execute('''
                INSERT INTO suppliers (supplier_id, supplier_name, contact_person, phone, email, address, payment_terms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', s)
        
        # Insert validated sample products
        products = [
            ('P001', 'Fresh Milk 1L', 'Dairy', 1.50, 1.20, 50),
            ('P002', 'White Bread', 'Bakery', 2.00, 1.50, 30),
            ('P003', 'Eggs Dozen', 'Dairy', 3.00, 2.40, 40)
        ]
        
        for p in products:
            # Validate prices
            if p[3] <= 0 or p[4] <= 0:
                st.warning(f"⚠️ Skipping product with invalid price: {p}")
                continue
            cursor.execute('''
                INSERT INTO products (product_code, product_name, category, unit_price, cost_price, reorder_level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', p)
        
        conn.commit()
        st.success(" Sample data loaded into SQLite!")
        
    except Exception as e:
        st.error(f"Error adding sample data: {e}")
    finally:
        conn.close()


# ============================================
# DATA FETCHING FUNCTIONS WITH VALIDATION
# ============================================

def get_suppliers_sqlite():
    """Get suppliers from SQLite with validation"""
    try:
        conn = sqlite3.connect('supermarket.db')
        df = pd.read_sql_query("SELECT * FROM suppliers ORDER BY supplier_name", conn)
        conn.close()
        
        # Validate data
        if df.empty:
            print(" No suppliers found")
        return df
    except Exception as e:
        print(f" Error fetching suppliers: {e}")
        return pd.DataFrame()


def get_products_sqlite():
    """Get products from SQLite with validation"""
    try:
        conn = sqlite3.connect('supermarket.db')
        df = pd.read_sql_query("SELECT * FROM products ORDER BY product_name", conn)
        conn.close()
        return df
    except Exception as e:
        print(f" Error fetching products: {e}")
        return pd.DataFrame()