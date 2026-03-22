# dashboard/pages/segments.py
import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection
from scripts.segmentation import CustomerSegmentation
import plotly.express as px
import pandas as pd

SEGMENT_COLORS = {
    'VIP Customer':     '#f39c12',
    'High Value':       '#9b59b6',
    'Regular Customer': '#2ecc71',
    'At Risk':          '#e74c3c',
    'Occasional':       '#3498db',
    'New Customer':     '#1abc9c',
    'Churned':          '#95a5a6',
}

def show_segments():
    st.title("👥 Customer Segments")
    st.markdown("Analyse and view customer groups based on purchase behaviour.")
    st.divider()

    db = DatabaseConnection()

    # ── Run Segmentation Button ───────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Segment Overview")
    with col2:
        if st.button("🔄 Run Analysis", type="primary", use_container_width=True):
            with st.spinner("Analysing customers..."):
                seg     = CustomerSegmentation()
                results = seg.run()
                if results:
                    st.success(f"✅ Segmented {len(results)} customers!")
                    st.rerun()
                else:
                    st.error("No customers found.")

    # ── Segment Chart + Table ─────────────────────────────
    seg_data = db.fetch_all("""
        SELECT cs.segment_name, COUNT(csa.customer_id) as count
        FROM customer_segments cs
        LEFT JOIN customer_segment_assignment csa ON cs.segment_id = csa.segment_id
        GROUP BY cs.segment_name
        HAVING COUNT(csa.customer_id) > 0
        ORDER BY count DESC
    """)

    if not seg_data:
        st.info("No segments yet. Click 'Run Analysis' above.")
        return

    df_seg = pd.DataFrame(seg_data, columns=['Segment', 'Count'])

    col_chart, col_stats = st.columns([1, 1])
    with col_chart:
        fig = px.pie(df_seg, values='Count', names='Segment',
                     color_discrete_sequence=px.colors.qualitative.Bold,
                     hole=0.35)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col_stats:
        st.markdown("### Segment Summary")
        for _, row in df_seg.iterrows():
            color = SEGMENT_COLORS.get(row['Segment'], '#888')
            st.markdown(
                f"<div style='padding:8px;margin:4px 0;border-left:4px solid {color};"
                f"background:#f8f9fa;border-radius:4px;'>"
                f"<strong>{row['Segment']}</strong> — {row['Count']} customers</div>",
                unsafe_allow_html=True
            )

    st.divider()

    # ── Filter by Segment ─────────────────────────────────
    st.subheader("Browse Customers by Segment")
    segments_list = ['All'] + [row[0] for row in seg_data]
    selected_seg  = st.selectbox("Filter by segment", segments_list)

    if selected_seg == 'All':
        customers = db.fetch_all("""
            SELECT c.customer_id, c.first_name, c.email,
                   cs.segment_name,
                   COUNT(DISTINCT t.transaction_id) as tx_count,
                   COALESCE(SUM(t.total_amount), 0) as total_spent,
                   c.email_notification_enabled
            FROM customers c
            JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
            JOIN customer_segments cs ON csa.segment_id = cs.segment_id
            LEFT JOIN transactions t ON c.customer_id = t.customer_id
            WHERE c.is_active = TRUE
            GROUP BY c.customer_id, c.first_name, c.email,
                     cs.segment_name, c.email_notification_enabled
            ORDER BY total_spent DESC
        """)
    else:
        customers = db.fetch_all("""
            SELECT c.customer_id, c.first_name, c.email,
                   cs.segment_name,
                   COUNT(DISTINCT t.transaction_id) as tx_count,
                   COALESCE(SUM(t.total_amount), 0) as total_spent,
                   c.email_notification_enabled
            FROM customers c
            JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
            JOIN customer_segments cs ON csa.segment_id = cs.segment_id
            LEFT JOIN transactions t ON c.customer_id = t.customer_id
            WHERE cs.segment_name = %s AND c.is_active = TRUE
            GROUP BY c.customer_id, c.first_name, c.email,
                     cs.segment_name, c.email_notification_enabled
            ORDER BY total_spent DESC
        """, [selected_seg])

    if customers:
        df_c = pd.DataFrame(customers,
                            columns=['ID','Name','Email','Segment',
                                     'Transactions','Total Spent','Email On'])
        df_c['Total Spent'] = df_c['Total Spent'].apply(
            lambda x: f"Rs.{float(x):,.2f}"
        )
        df_c['Email On'] = df_c['Email On'].apply(
            lambda x: '✅' if x else '❌'
        )
        st.dataframe(df_c, use_container_width=True, hide_index=True)
    else:
        st.info("No customers in this segment yet.")