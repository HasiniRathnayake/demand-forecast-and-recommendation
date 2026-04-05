# pages/product_performance.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import numpy as np
from database import get_db_connection

st.set_page_config(page_title="Product Performance", layout="wide")

# Helper functions to detect connection type
def is_supabase(conn):
    return hasattr(conn, 'table') and callable(getattr(conn, 'table'))

def is_sqlite(conn):
    return hasattr(conn, 'cursor') and hasattr(conn, 'execute')

# Get connection and determine type
conn = get_db_connection()
conn_type = "supabase" if is_supabase(conn) else "sqlite" if is_sqlite(conn) else "unknown"

st.markdown('<div class="section-header">📦 Product Performance Analysis</div>', unsafe_allow_html=True)
st.caption("Analyze discrepancy patterns and performance metrics by product")

# ============================================
# GET DATA BASED ON CONNECTION TYPE
# ============================================
if conn_type == "supabase":
    # Supabase version
    try:
        # Get deliveries with product info
        response = conn.table("deliveries")\
            .select("""
                delivery_date,
                invoice_number,
                supplier_id,
                suppliers!inner(supplier_name),
                delivery_items(
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
            .execute()
        
        # Parse data
        data = []
        for delivery in response.data:
            delivery_date = delivery.get('delivery_date')
            invoice = delivery.get('invoice_number')
            supplier_name = delivery.get('suppliers', {}).get('supplier_name', 'Unknown')
            
            for item in delivery.get('delivery_items', []):
                product_info = item.get('products', {})
                data.append({
                    'delivery_date': delivery_date,
                    'invoice_number': invoice,
                    'supplier_name': supplier_name,
                    'product_code': item.get('product_code'),
                    'product_name': product_info.get('product_name', 'Unknown'),
                    'category': product_info.get('category', 'Unknown'),
                    'cost_price': float(product_info.get('cost_price', 0)),
                    'unit_price': float(product_info.get('unit_price', 0)),
                    'ordered_quantity': float(item.get('billed_quantity', 0)),
                    'received_quantity': float(item.get('received_quantity', 0)),
                    'discrepancy_quantity': float(item.get('received_quantity', 0)) - float(item.get('billed_quantity', 0))
                })
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            df['discrepancy_percentage'] = (df['discrepancy_quantity'] / df['ordered_quantity'] * 100).round(1)
            df['financial_impact'] = df['discrepancy_quantity'] * df['cost_price']
            
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        df = pd.DataFrame()

elif conn_type == "sqlite":
    # SQLite version
    query = """
        SELECT 
            d.delivery_date,
            d.invoice_number,
            d.product_code,
            p.product_name,
            p.category,
            p.cost_price,
            p.unit_price,
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
    st.error("Unknown database connection type")
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
choices = ['✅ Accurate', '⚠️ Short Shipped', '📦 Over Delivered']
df['status'] = pd.Series(pd.Categorical(np.select(conditions, choices, default='Unknown')))

# ============================================
# SIDEBAR FILTERS
# ============================================
st.sidebar.markdown("### 🎯 Filters")

# Date range filter
min_date = pd.to_datetime(df['delivery_date']).min().date()
max_date = pd.to_datetime(df['delivery_date']).max().date()

col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input("From", value=min_date)
with col2:
    end_date = st.date_input("To", value=max_date)

# Category filter
categories = ['All'] + sorted(df['category'].dropna().unique().tolist())
selected_category = st.sidebar.selectbox("Category", categories)

# Product filter
products = ['All'] + sorted(df['product_name'].dropna().unique().tolist())
selected_product = st.sidebar.selectbox("Product", products)

# Supplier filter
suppliers = ['All'] + sorted(df['supplier_name'].dropna().unique().tolist())
selected_supplier = st.sidebar.selectbox("Supplier", suppliers)

# Apply filters
filtered_df = df[
    (pd.to_datetime(df['delivery_date']).dt.date >= start_date) &
    (pd.to_datetime(df['delivery_date']).dt.date <= end_date)
]

if selected_category != 'All':
    filtered_df = filtered_df[filtered_df['category'] == selected_category]

if selected_product != 'All':
    filtered_df = filtered_df[filtered_df['product_name'] == selected_product]

if selected_supplier != 'All':
    filtered_df = filtered_df[filtered_df['supplier_name'] == selected_supplier]

if filtered_df.empty:
    st.warning("No data matches your filters")
    st.stop()

# ============================================
# KPI METRICS
# ============================================
st.markdown("### 📊 Key Metrics")

col1, col2, col3, col4 = st.columns(4)

total_products = filtered_df['product_name'].nunique()
total_deliveries = len(filtered_df)
total_discrepancies = len(filtered_df[filtered_df['status'] != '✅ Accurate'])
total_financial = filtered_df['financial_impact'].sum()

with col1:
    st.metric("Products Analyzed", total_products)
with col2:
    st.metric("Total Deliveries", total_deliveries)
with col3:
    st.metric("Discrepancies", total_discrepancies)
with col4:
    st.metric("Financial Impact", f"LKR {abs(total_financial):,.2f}")

# ============================================
# PRODUCT RANKINGS
# ============================================
st.markdown("### 🏆 Product Rankings")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Highest Discrepancy", "💸 Highest Financial Loss", "📈 Most Frequent", "✅ Most Accurate"])

# Tab 1: Highest Discrepancy Rate
with tab1:
    product_rank = filtered_df.groupby('product_name').agg({
        'discrepancy_percentage': 'mean',
        'ordered_quantity': 'sum',
        'status': lambda x: (x != '✅ Accurate').sum(),
        'delivery_date': 'count'
    }).reset_index()
    product_rank.columns = ['Product', 'Avg Discrepancy %', 'Total Ordered', 'Issues', 'Deliveries']
    product_rank = product_rank.sort_values('Avg Discrepancy %', ascending=False).head(10)
    
    if not product_rank.empty:
        fig = px.bar(product_rank, x='Product', y='Avg Discrepancy %',
                     title='Top 10 Products by Discrepancy Rate',
                     color='Avg Discrepancy %',
                     color_continuous_scale=['green', 'yellow', 'red'])
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(product_rank, width='stretch')
    else:
        st.info("No data available")

# Tab 2: Highest Financial Loss
with tab2:
    loss_rank = filtered_df.groupby('product_name').agg({
        'financial_impact': 'sum',
        'ordered_quantity': 'sum',
        'status': lambda x: (x == '⚠️ Short Shipped').sum()
    }).reset_index()
    loss_rank.columns = ['Product', 'Financial Impact', 'Total Ordered', 'Short Shipments']
    loss_rank = loss_rank.sort_values('Financial Impact', ascending=True).head(10)
    
    if not loss_rank.empty:
        fig = px.bar(loss_rank, x='Product', y='Financial Impact',
                     title='Top 10 Products by Financial Loss',
                     color='Financial Impact',
                     color_continuous_scale=['red', 'yellow', 'green'])
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(loss_rank, width='stretch')
    else:
        st.info("No data available")

# Tab 3: Most Frequent Issues
with tab3:
    freq_rank = filtered_df.groupby('product_name').agg({
        'status': lambda x: (x != '✅ Accurate').count(),
        'delivery_date': 'count'
    }).reset_index()
    freq_rank.columns = ['Product', 'Issues', 'Total Deliveries']
    freq_rank['Issue Rate %'] = (freq_rank['Issues'] / freq_rank['Total Deliveries'] * 100).round(1)
    freq_rank = freq_rank.sort_values('Issues', ascending=False).head(10)
    
    if not freq_rank.empty:
        fig = px.bar(freq_rank, x='Product', y='Issues',
                     title='Products with Most Issues',
                     color='Issue Rate %',
                     color_continuous_scale=['green', 'yellow', 'red'])
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(freq_rank, width='stretch')
    else:
        st.info("No data available")

# Tab 4: Most Accurate
with tab4:
    accurate_rank = filtered_df.groupby('product_name').agg({
        'status': lambda x: (x == '✅ Accurate').sum(),
        'delivery_date': 'count'
    }).reset_index()
    accurate_rank.columns = ['Product', 'Accurate Deliveries', 'Total Deliveries']
    accurate_rank['Accuracy Rate %'] = (accurate_rank['Accurate Deliveries'] / accurate_rank['Total Deliveries'] * 100).round(1)
    accurate_rank = accurate_rank.sort_values('Accuracy Rate %', ascending=False).head(10)
    
    if not accurate_rank.empty:
        fig = px.bar(accurate_rank, x='Product', y='Accuracy Rate %',
                     title='Most Accurate Products',
                     color='Accuracy Rate %',
                     color_continuous_scale=['red', 'yellow', 'green'])
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(accurate_rank, width='stretch')
    else:
        st.info("No data available")

# ============================================
# CATEGORY ANALYSIS
# ============================================
st.markdown("### 🏷️ Category Performance")

col1, col2 = st.columns(2)

with col1:
    category_stats = filtered_df.groupby('category').agg({
        'discrepancy_percentage': 'mean',
        'financial_impact': 'sum',
        'product_name': 'count'
    }).reset_index()
    category_stats.columns = ['Category', 'Avg Discrepancy %', 'Financial Impact', 'Transactions']
    
    if not category_stats.empty:
        fig = px.bar(category_stats, x='Category', y='Avg Discrepancy %',
                     title='Average Discrepancy by Category',
                     color='Avg Discrepancy %',
                     color_continuous_scale=['green', 'yellow', 'red'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No category data available")

with col2:
    if not category_stats.empty:
        fig = px.bar(category_stats, x='Category', y='Financial Impact',
                     title='Financial Impact by Category',
                     color='Financial Impact',
                     color_continuous_scale=['green', 'yellow', 'red'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No category data available")

# ============================================
# DETAILED PRODUCT TABLE
# ============================================
st.markdown("### 📋 Detailed Product Performance")

# Create summary table
product_summary = filtered_df.groupby(['product_name', 'category']).agg({
    'ordered_quantity': 'sum',
    'received_quantity': 'sum',
    'discrepancy_quantity': 'sum',
    'discrepancy_percentage': 'mean',
    'financial_impact': 'sum',
    'status': lambda x: (x != '✅ Accurate').sum(),
    'delivery_date': 'count'
}).reset_index()

product_summary.columns = [
    'Product', 'Category', 'Total Ordered', 'Total Received', 
    'Net Discrepancy', 'Avg Discrepancy %', 'Financial Impact', 
    'Issues', 'Deliveries'
]

product_summary['Accuracy Rate %'] = ((product_summary['Deliveries'] - product_summary['Issues']) / product_summary['Deliveries'] * 100).round(1)

# Format columns
product_summary['Total Ordered'] = product_summary['Total Ordered'].apply(lambda x: f"{x:,.0f}")
product_summary['Total Received'] = product_summary['Total Received'].apply(lambda x: f"{x:,.0f}")
product_summary['Net Discrepancy'] = product_summary['Net Discrepancy'].apply(lambda x: f"{x:+,.0f}")
product_summary['Avg Discrepancy %'] = product_summary['Avg Discrepancy %'].apply(lambda x: f"{x:+.1f}%")
product_summary['Financial Impact'] = product_summary['Financial Impact'].apply(lambda x: f"LKR {x:,.2f}")
product_summary['Issues'] = product_summary['Issues'].apply(lambda x: f"{x}")
product_summary['Accuracy Rate %'] = product_summary['Accuracy Rate %'].apply(lambda x: f"{x:.1f}%")

st.dataframe(product_summary, width='stretch')

# ============================================
# EXPORT BUTTON
# ============================================
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    csv = product_summary.to_csv(index=False)
    st.download_button(
        label="📥 Export Product Performance Report (CSV)",
        data=csv,
        file_name=f"product_performance_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )