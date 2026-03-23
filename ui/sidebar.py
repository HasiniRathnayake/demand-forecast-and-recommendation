"""
ui/sidebar.py
Author : IT24103258
"""

from __future__ import annotations
from datetime import date, timedelta
import streamlit as st


def render_sidebar() -> tuple[date, date]:
    with st.sidebar:
        st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

        st.markdown("### ♻️ Waste & Performance Monitor")
        st.markdown("---")
        st.markdown("**Date Range**")

        period = st.selectbox(
            "Period",
            ["All Time", "Today", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom"],
            label_visibility="collapsed",
            key="wpm_period",
        )

        today = date.today()

        if period == "Custom":
            start = st.date_input("Start Date", today - timedelta(days=30), key="wpm_start")
            end   = st.date_input("End Date", today, key="wpm_end")
            if start > end:
                st.warning("Start date is after end date.")
                start, end = end, start
        elif period == "All Time":
            start, end = date(2000, 1, 1), today
        elif period == "Today":
            start, end = today, today
        elif period == "Last 7 Days":
            start, end = today - timedelta(7), today
        elif period == "Last 30 Days":
            start, end = today - timedelta(30), today
        else:
            start, end = today - timedelta(90), today

    return start, end