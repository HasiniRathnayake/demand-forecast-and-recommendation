# dashboard/pages/home.py
import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection
import plotly.express as px
import pandas as pd


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

def show_home():
    st.title("🏠 Dashboard Overview")
    st.markdown("Welcome to the **Sunrise Super Loyalty Manager**")
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

    with col1:
        st.metric("Total Customers",  total_customers[0] if total_customers else 0)
    with col2:
        st.metric("Email Eligible",   email_eligible[0]  if email_eligible  else 0)
    with col3:
        st.metric("Total Transactions", total_tx[0]      if total_tx        else 0)
    with col4:
        rev = float(total_revenue[0]) if total_revenue else 0
        st.metric("Total Revenue", f"Rs.{rev:,.0f}")

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
        st.subheader("Revenue by Month")
        rev_data = db.fetch_all("""
            SELECT TO_CHAR(transaction_date,'Mon YYYY') as month,
                   SUM(total_amount) as revenue,
                   DATE_TRUNC('month', transaction_date) as sort_date
            FROM transactions
            GROUP BY month, sort_date
            ORDER BY sort_date
        """)
        if rev_data:
            df2 = pd.DataFrame(rev_data, columns=['Month', 'Revenue', 'Sort'])
            fig2 = px.bar(df2, x='Month', y='Revenue',
                          color_discrete_sequence=['#2ecc71'])
            fig2.update_layout(height=350, margin=dict(t=20, b=20))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No transaction data found.")

    # ── Recent Transactions ───────────────────────────────
    st.subheader("Recent Transactions")
    recent = db.fetch_all("""
        SELECT t.transaction_id, c.first_name, t.transaction_date,
               t.total_amount
        FROM transactions t
        JOIN customers c ON t.customer_id = c.customer_id
        ORDER BY t.transaction_date DESC
        LIMIT 10
    """)
    if recent:
        df3 = pd.DataFrame(recent,
                           columns=['Transaction ID','Customer','Date','Amount'])
        df3['Amount'] = df3['Amount'].apply(lambda x: f"Rs.{float(x):,.2f}")
        st.dataframe(df3, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions found.")