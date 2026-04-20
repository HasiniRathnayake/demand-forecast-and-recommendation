# dashboard/pages/home.py
import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection
from ui.styles import render_page_heading
import plotly.express as px
import pandas as pd

TASTE_LABELS = {
    'balanced shoppers': '🥦 balanced shoppers',
    'fresh & protein lovers': '🐟 fresh & protein lovers',
    'family & baby care': '👶 family & baby care',
    'drink & health focused': '🥤 drink & health focused',
}


def _assignment_segment_column():
    db = DatabaseConnection()
    cols = db.fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'customer_segment_assignment'
        """
    )
    names = {c[0] for c in cols}
    if 'segment_id' in names:
        return 'segment_id'
    if 'segment' in names:
        return 'segment'
    return 'segment_id'


def _assignment_taste_column():
    db = DatabaseConnection()
    cols = db.fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'customer_segment_assignment'
        """
    )
    names = {c[0] for c in cols}
    if 'product_preference' in names:
        return 'product_preference'
    if 'segment_name' in names:
        return 'segment_name'
    return None


def _normalize_taste_label(raw_label):
    normalized = str(raw_label or '').strip().lower()
    if not normalized:
        return ''
    for key, label in TASTE_LABELS.items():
        if key in normalized:
            return label
    return str(raw_label).strip()

def show_home():
    render_page_heading("Dashboard Overview")
    st.divider()

    db = DatabaseConnection()

    # ── KPI Row ──────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    total_customers = db.fetch_one("SELECT COUNT(*) FROM customers WHERE is_active = TRUE")
    email_eligible  = db.fetch_one("""
        SELECT COUNT(*) FROM customers
        WHERE email_notification_enabled = TRUE
        AND promotional_emails_allowed = TRUE
        AND is_active = TRUE
    """)
    total_tx        = db.fetch_one("SELECT COUNT(*) FROM transactions")
    total_revenue   = db.fetch_one("SELECT COALESCE(SUM(total_amount),0) FROM transactions")
    monthly_avg_rev = db.fetch_one("""
        SELECT COALESCE(AVG(monthly_revenue), 0)
        FROM (
            SELECT DATE_TRUNC('month', transaction_date) AS month,
                   SUM(total_amount) AS monthly_revenue
            FROM transactions
            GROUP BY DATE_TRUNC('month', transaction_date)
        ) m
    """)

    customers_n = int(total_customers[0]) if total_customers else 0
    eligible_n = int(email_eligible[0]) if email_eligible else 0
    tx_n = int(total_tx[0]) if total_tx else 0
    rev_n = float(total_revenue[0]) if total_revenue else 0.0
    avg_monthly_rev = float(monthly_avg_rev[0]) if monthly_avg_rev else 0.0
    avg_basket = (rev_n / tx_n) if tx_n > 0 else 0.0
    avg_tx_per_customer = (tx_n / customers_n) if customers_n > 0 else 0.0
    eligible_rate = (eligible_n / customers_n * 100) if customers_n > 0 else 0.0

    with col1:
        st.metric("Avg Basket Size", f"Rs.{avg_basket:,.0f}")
    with col2:
        st.metric("Avg Monthly Revenue", f"Rs.{avg_monthly_rev:,.0f}")
    with col3:
        st.metric("Avg Tx per Customer", f"{avg_tx_per_customer:.2f}")
    with col4:
        st.metric("Promo-Eligible Rate", f"{eligible_rate:.1f}%")

    st.caption(
        f"Historical base: {customers_n} active customers, {tx_n} transactions, total revenue Rs.{rev_n:,.0f}."
    )

    st.divider()

    # ── Charts Row ───────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Customer Segments")
        segment_col = _assignment_segment_column()
        seg_data = db.fetch_all(f"""
            SELECT cs.segment_name, COUNT(csa.customer_id) as count
            FROM customer_segments cs
            LEFT JOIN customer_segment_assignment csa ON cs.segment_id = csa.{segment_col}
            GROUP BY cs.segment_name
            HAVING COUNT(csa.customer_id) > 0
            ORDER BY count DESC
        """)
        if seg_data:
            df = pd.DataFrame(seg_data, columns=['Segment', 'Count'])
            fig = px.pie(df, values='Count', names='Segment',
                         color_discrete_sequence=px.colors.qualitative.Bold,
                         hole=0.35)
            fig.update_layout(height=350, margin=dict(t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No segments yet. Go to Customer Segments and click Analyse.")

    with col_right:
        st.subheader("Taste Preferences")
        taste_col = _assignment_taste_column()
        if taste_col:
            taste_data = db.fetch_all(f"""
                SELECT LOWER(TRIM(csa.{taste_col}::text)) as preference,
                       COUNT(DISTINCT csa.customer_id) as count
                FROM customer_segment_assignment csa
                WHERE csa.{taste_col} IS NOT NULL
                  AND TRIM(csa.{taste_col}::text) <> ''
                GROUP BY LOWER(TRIM(csa.{taste_col}::text))
                ORDER BY count DESC
                LIMIT 10
            """)
            taste_data = [(_normalize_taste_label(row[0]), row[1]) for row in taste_data]
        else:
            taste_data = []

        if taste_data:
            df2 = pd.DataFrame(taste_data, columns=['Preference', 'Count'])
            fig2 = px.bar(
                df2,
                x='Count',
                y='Preference',
                orientation='h',
                color='Count',
                color_continuous_scale='Blues',
            )
            fig2.update_layout(height=350, margin=dict(t=20, b=20), yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No taste preference data found.")

    # ── Top products by segment ───────────────────────────
    st.subheader("Top Products by Segment")
    segment_col = _assignment_segment_column()
    top_products = db.fetch_all(f"""
        SELECT
            cs.segment_name,
            p.product_name,
            COALESCE(SUM(ti.quantity), 0) as total_qty,
            COUNT(DISTINCT t.transaction_id) as tx_count
        FROM customer_segment_assignment csa
        JOIN customer_segments cs ON csa.{segment_col} = cs.segment_id
        JOIN customers c ON csa.customer_id = c.customer_id
        JOIN transactions t ON c.customer_id = t.customer_id
        JOIN transaction_items ti ON t.transaction_id = ti.transaction_id
        JOIN product_catalog p ON ti.product_code = p.product_code
        WHERE c.is_active = TRUE
        GROUP BY cs.segment_name, p.product_name
        ORDER BY cs.segment_name, total_qty DESC
    """)

    if top_products:
        df_top = pd.DataFrame(top_products, columns=['Segment', 'Product', 'Total Qty', 'Transactions'])
        df_top = df_top.sort_values(['Segment', 'Total Qty'], ascending=[True, False])
        df_top = df_top.groupby('Segment', as_index=False, group_keys=False).head(5)
        st.dataframe(df_top, use_container_width=True, hide_index=True)
    else:
        st.info("No product-level segment history found.")