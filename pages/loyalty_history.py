# dashboard/pages/email_history.py
import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.db_connection import DatabaseConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def show_email_history():
    st.title("📧 Email History")
    st.markdown("Track all campaigns sent to customers.")
    st.divider()

    db = DatabaseConnection()

    # ── KPI Row ───────────────────────────────────────────
    total_sent  = db.fetch_one("SELECT COUNT(*) FROM email_log")
    total_open  = db.fetch_one("SELECT COUNT(*) FROM email_log WHERE opened = TRUE")
    total_click = db.fetch_one("SELECT COUNT(*) FROM email_log WHERE clicked = TRUE")
    total_fail  = db.fetch_one(
        "SELECT COUNT(*) FROM email_log WHERE delivery_status = 'failed'"
    )

    sent_count  = total_sent[0]  if total_sent  else 0
    open_count  = total_open[0]  if total_open  else 0
    click_count = total_click[0] if total_click else 0
    fail_count  = total_fail[0]  if total_fail  else 0

    open_rate  = round((open_count  / sent_count) * 100, 1) if sent_count > 0 else 0
    click_rate = round((click_count / sent_count) * 100, 1) if sent_count > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Sent",   sent_count)
    with col2:
        st.metric("Opened",       open_count)
    with col3:
        st.metric("Open Rate",    f"{open_rate}%")
    with col4:
        st.metric("Clicked",      click_count)
    with col5:
        st.metric("Click Rate",   f"{click_rate}%")

    st.divider()

    if sent_count == 0:
        st.info("No emails sent yet. Go to Campaign Builder to send your first campaign.")
        return

    # ── Charts Row ────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📊 Engagement Funnel")
        fig = go.Figure(go.Funnel(
            y=['Sent', 'Opened', 'Clicked'],
            x=[sent_count, open_count, click_count],
            marker=dict(color=['#2ecc71', '#f39c12', '#e74c3c']),
            textinfo="value+percent initial"
        ))
        fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("📈 Emails Sent Over Time")
        chart_data = db.fetch_all("""
            SELECT DATE(sent_date) as day, COUNT(*) as count
            FROM email_log
            GROUP BY day ORDER BY day
        """)
        if chart_data:
            df2 = pd.DataFrame(chart_data, columns=['Date', 'Emails Sent'])
            fig2 = px.area(df2, x='Date', y='Emails Sent',
                           color_discrete_sequence=['#2ecc71'])
            fig2.update_layout(height=300, margin=dict(t=20, b=20))
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Email Log Table ───────────────────────────────────
    st.subheader("📋 All Sent Emails")

    # Filter
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        search = st.text_input("Search by customer name or email", placeholder="e.g. Kamal")
    with col_f2:
        status_filter = st.selectbox("Filter by status", ["All", "Sent", "Failed"])

    logs = db.fetch_all("""
        SELECT el.email_log_id,
               c.first_name,
               c.email,
               el.email_type,
               el.subject,
               TO_CHAR(el.sent_date, 'DD Mon YYYY HH24:MI') as sent,
               el.delivery_status,
               el.opened,
               el.clicked
        FROM email_log el
        JOIN customers c ON el.customer_id = c.customer_id
        ORDER BY el.sent_date DESC
        LIMIT 200
    """)

    if logs:
        df = pd.DataFrame(logs, columns=[
            'ID', 'Customer', 'Email', 'Type',
            'Subject', 'Sent', 'Status', 'Opened', 'Clicked'
        ])

        # Apply filters
        if search:
            df = df[
                df['Customer'].str.contains(search, case=False, na=False) |
                df['Email'].str.contains(search, case=False, na=False)
            ]
        if status_filter != "All":
            df = df[df['Status'] == status_filter.lower()]

        df['Status']  = df['Status'].apply(
            lambda x: '✅ Sent' if x == 'sent' else '❌ Failed'
        )
        df['Opened']  = df['Opened'].apply(lambda x: '✅' if x else '—')
        df['Clicked'] = df['Clicked'].apply(lambda x: '✅' if x else '—')

        st.markdown(f"Showing **{len(df)}** records")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No emails found.")