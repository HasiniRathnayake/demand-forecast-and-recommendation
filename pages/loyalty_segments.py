# dashboard/pages/segments.py
import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection
from scripts.segmentation import CustomerSegmentation
from ui.styles import render_page_heading
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
    # Taste preferences
    '🥦 balanced shoppers': '#27ae60',
    '🐟 fresh & protein lovers': '#e67e22',
    '👶 family & baby care': '#9b59b6',
    '🥤 drink & health focused': '#3498db',
}

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

def show_segments():
    render_page_heading("Customer Segments")
    st.divider()

    db = DatabaseConnection()

    # ── Run Segmentation Button ───────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Segment Overview")
    with col2:
        clustering_mode = st.selectbox("Clustering Mode", ["RFM", "Taste Preferences"], key="clustering_mode")
        if st.button("🔄 Sync Cluster Segments", type="primary", use_container_width=True):
            # ── VALIDATION BEFORE ANALYSIS ──────────────────────────
            analysis_errors = []
            
            # Check if analysis already running (prevent duplicate runs)
            if st.session_state.get("analysis_running", False):
                st.warning("⏳ Analysis is already running. Please wait...")
                st.stop()
            
            # Check if customer data exists
            customer_count = db.fetch_one("SELECT COUNT(*) FROM customers WHERE is_active = TRUE")
            if not customer_count or customer_count[0] == 0:
                analysis_errors.append("❌ No active customers found in database")
            
            # Display validation errors
            if analysis_errors:
                for error in analysis_errors:
                    st.error(error)
                st.stop()
            
            # Mark analysis as running
            st.session_state.analysis_running = True
            
            mode = 'rfm' if clustering_mode == "RFM" else 'taste'
            with st.spinner(f"Syncing {clustering_mode.lower()} cluster-based customer segments..."):
                try:
                    seg     = CustomerSegmentation()
                    results = seg.run(mode=mode)
                    if results:
                        st.success(f"✅ Synced {len(results)} clustered customers!")
                        st.session_state.analysis_running = False
                        st.rerun()
                    else:
                        st.error("❌ Cluster sync failed: no customer cluster rows found.")
                        st.session_state.analysis_running = False
                except Exception as e:
                    st.error(f"❌ Error during segmentation: {str(e)}")
                    st.session_state.analysis_running = False

def show_segments():
    render_page_heading("Customer Segments")
    st.divider()

    db = DatabaseConnection()

    # ── Run Segmentation Button ───────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Segment Overview")
    with col2:
        clustering_mode = st.selectbox("Clustering Mode", ["RFM", "Taste Preferences"], key="clustering_mode")
        if st.button("🔄 Sync Cluster Segments", type="primary", use_container_width=True):
            # ── VALIDATION BEFORE ANALYSIS ──────────────────────────
            analysis_errors = []
            
            # Check if analysis already running (prevent duplicate runs)
            if st.session_state.get("analysis_running", False):
                st.warning("⏳ Analysis is already running. Please wait...")
                st.stop()
            
            # Check if customer data exists
            customer_count = db.fetch_one("SELECT COUNT(*) FROM customers WHERE is_active = TRUE")
            if not customer_count or customer_count[0] == 0:
                analysis_errors.append("❌ No active customers found in database")
            
            # Display validation errors
            if analysis_errors:
                for error in analysis_errors:
                    st.error(error)
                st.stop()
            
            # Mark analysis as running
            st.session_state.analysis_running = True
            
            mode = 'rfm' if clustering_mode == "RFM" else 'taste'
            with st.spinner(f"Syncing {clustering_mode.lower()} cluster-based customer segments..."):
                try:
                    seg     = CustomerSegmentation()
                    results = seg.run(mode=mode)
                    if results:
                        st.success(f"✅ Synced {len(results)} clustered customers!")
                        st.session_state.analysis_running = False
                        st.rerun()
                    else:
                        st.error("❌ Cluster sync failed: no customer cluster rows found.")
                        st.session_state.analysis_running = False
                except Exception as e:
                    st.error(f"❌ Error during segmentation: {str(e)}")
                    st.session_state.analysis_running = False

    # ── Segment Chart + Table ─────────────────────────────
    if clustering_mode == "RFM":
        segment_col = _assignment_segment_column()
        seg_data = db.fetch_all(f"""
            SELECT cs.segment_name, COUNT(csa.customer_id) as count
            FROM customer_segments cs
            LEFT JOIN customer_segment_assignment csa ON cs.segment_id = csa.{segment_col}
            GROUP BY cs.segment_name
            HAVING COUNT(csa.customer_id) > 0
            ORDER BY count DESC
        """)
        title = "Customer Segments"
        filter_label = "segment"
        filter_options = ['All'] + [row[0] for row in seg_data] if seg_data else ['All']
    else:
        taste_col = _assignment_taste_column()
        if not taste_col:
            st.info("No taste preference column found in customer_segment_assignment.")
            return

        seg_data = db.fetch_all(f"""
            SELECT LOWER(TRIM(csa.{taste_col}::text)) as preference,
                   COUNT(DISTINCT csa.customer_id) as count
            FROM customer_segment_assignment csa
            WHERE csa.{taste_col} IS NOT NULL
              AND TRIM(csa.{taste_col}::text) <> ''
            GROUP BY LOWER(TRIM(csa.{taste_col}::text))
            ORDER BY count DESC
        """)
        seg_data = [(_normalize_taste_label(row[0]), row[1]) for row in seg_data]
        title = "Taste Preferences"
        filter_label = "taste preference"
        filter_options = ['All'] + [row[0] for row in seg_data] if seg_data else ['All']

    if not seg_data:
        st.info(f"No {title.lower()} yet. Click 'Sync Cluster Segments' above.")
        return

    df_seg = pd.DataFrame(seg_data, columns=['Group', 'Count'])

    col_chart, col_stats = st.columns([1, 1])
    with col_chart:
        fig = px.pie(df_seg, values='Count', names='Group',
                     color_discrete_sequence=px.colors.qualitative.Bold,
                     hole=0.35)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col_stats:
        st.markdown(f"### {title} Summary")
        for _, row in df_seg.iterrows():
            color = SEGMENT_COLORS.get(row['Group'], '#888')
            st.markdown(
                f"<div style='padding:8px;margin:4px 0;border-left:4px solid {color};"
                f"background:#f8f9fa;border-radius:4px;'>"
                f"<strong>{row['Group']}</strong> — {row['Count']} customers</div>",
                unsafe_allow_html=True
            )

    st.divider()

    # ── Filter by Segment ─────────────────────────────────
    st.subheader(f"Browse Customers by {title}")
    selected_seg  = st.selectbox(f"Filter by {filter_label}", filter_options)

    if clustering_mode == "RFM":
        if selected_seg == 'All':
            customers = db.fetch_all(f"""
                SELECT c.customer_id, c.first_name, c.email,
                       cs.segment_name,
                       COUNT(DISTINCT t.transaction_id) as tx_count,
                       COALESCE(SUM(t.total_amount), 0) as total_spent,
                       c.email_notification_enabled
                FROM customers c
                JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
                JOIN customer_segments cs ON csa.{segment_col} = cs.segment_id
                LEFT JOIN transactions t ON c.customer_id = t.customer_id
                WHERE c.is_active = TRUE
                GROUP BY c.customer_id, c.first_name, c.email,
                         cs.segment_name, c.email_notification_enabled
                ORDER BY total_spent DESC
            """)
        else:
            customers = db.fetch_all(f"""
                SELECT c.customer_id, c.first_name, c.email,
                       cs.segment_name,
                       COUNT(DISTINCT t.transaction_id) as tx_count,
                       COALESCE(SUM(t.total_amount), 0) as total_spent,
                       c.email_notification_enabled
                FROM customers c
                JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
                JOIN customer_segments cs ON csa.{segment_col} = cs.segment_id
                LEFT JOIN transactions t ON c.customer_id = t.customer_id
                WHERE cs.segment_name = %s AND c.is_active = TRUE
                GROUP BY c.customer_id, c.first_name, c.email,
                         cs.segment_name, c.email_notification_enabled
                ORDER BY total_spent DESC
            """, [selected_seg])
    else:
        taste_col = _assignment_taste_column()
        if selected_seg == 'All':
            customers = db.fetch_all(f"""
                SELECT c.customer_id, c.first_name, c.email,
                       LOWER(TRIM(csa.{taste_col}::text)) as taste,
                       COUNT(DISTINCT t.transaction_id) as tx_count,
                       COALESCE(SUM(t.total_amount), 0) as total_spent,
                       c.email_notification_enabled
                FROM customers c
                JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
                LEFT JOIN transactions t ON c.customer_id = t.customer_id
                WHERE c.is_active = TRUE
                GROUP BY c.customer_id, c.first_name, c.email,
                         LOWER(TRIM(csa.{taste_col}::text)), c.email_notification_enabled
                ORDER BY total_spent DESC
            """)
        else:
            customers = db.fetch_all(f"""
                SELECT c.customer_id, c.first_name, c.email,
                       LOWER(TRIM(csa.{taste_col}::text)) as taste,
                       COUNT(DISTINCT t.transaction_id) as tx_count,
                       COALESCE(SUM(t.total_amount), 0) as total_spent,
                       c.email_notification_enabled
                FROM customers c
                JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
                LEFT JOIN transactions t ON c.customer_id = t.customer_id
                WHERE LOWER(TRIM(csa.{taste_col}::text)) = %s AND c.is_active = TRUE
                GROUP BY c.customer_id, c.first_name, c.email,
                         LOWER(TRIM(csa.{taste_col}::text)), c.email_notification_enabled
                ORDER BY total_spent DESC
            """, [selected_seg.strip().lower()])

    if customers:
        df_c = pd.DataFrame(customers,
                            columns=['ID','Name','Email','Group',
                                     'Transactions','Total Spent','Email On'])
        if clustering_mode == "Taste Preferences":
            df_c['Group'] = df_c['Group'].apply(_normalize_taste_label)
        df_c['Total Spent'] = df_c['Total Spent'].apply(
            lambda x: f"Rs.{float(x):,.2f}"
        )
        df_c['Email On'] = df_c['Email On'].apply(
            lambda x: '✅' if x else '❌'
        )
        st.dataframe(df_c, use_container_width=True, hide_index=True)
    else:
        st.info("No customers in this group yet.")