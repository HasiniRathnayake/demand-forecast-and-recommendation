# pages/customer_dashboard.py
import streamlit as st
import sys, os
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection
from scripts.apriori_engine import AprioriEngine
import pandas as pd
import plotly.express as px
from datetime import date, datetime, timedelta

# ── Segment config ────────────────────────────────────────────────────────────
SEGMENT_COLORS = {
    'VIP Customer':     '#d4ac0d',
    'High Value':       '#7C3AED',
    'Regular Customer': '#059669',
    'At Risk':          '#DC2626',
    'Occasional':       '#2563EB',
    'New Customer':     '#0891B2',
    'Churned':          '#64748B',
}
SEGMENT_FRIENDLY = {
    'VIP Customer':     '⭐ VIP Member',
    'High Value':       '💎 Premium Member',
    'Regular Customer': '🛒 Loyal Member',
    'At Risk':          '🛒 Valued Member',
    'Occasional':       '🛍️ Special Member',
    'New Customer':     '🆕 New Member',
    'Churned':          '🛒 Valued Member',
}
SEGMENT_PERKS = {
    'VIP Customer':     ['20% OFF all purchases',
                         'Priority customer service',
                         'Exclusive VIP-only offers',
                         'Early access to new products'],
    'High Value':       ['15% OFF all purchases',
                         'Premium member offers',
                         'Free delivery on large orders'],
    'Regular Customer': ['10% OFF selected items',
                         'Weekly special deals',
                         'Loyalty points on every purchase'],
    'At Risk':          ['25% OFF welcome back offer',
                         'Special comeback deals',
                         'Personalised recommendations'],
    'Occasional':       ['15% OFF next purchase',
                         'Monthly special offers'],
    'New Customer':     ['10% OFF first purchase',
                         'Welcome gift offer',
                         'New member exclusive deals'],
    'Churned':          ['30% OFF comeback offer',
                         'We miss you special deals'],
}


# ── Cached data loaders ───────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _get_profile(customer_id):
    db = DatabaseConnection()
    return db.fetch_one("""
        SELECT c.customer_id, c.first_name, c.last_name, c.email,
               c.join_date, c.last_active_date,
               cs.segment_name
        FROM customers c
        LEFT JOIN customer_segment_assignment csa
               ON c.customer_id = csa.customer_id
        LEFT JOIN customer_segments cs
               ON csa.segment_id = cs.segment_id
        WHERE c.customer_id = %s
    """, [customer_id])


@st.cache_data(ttl=300, show_spinner=False)
def _get_purchases(customer_id):
    db = DatabaseConnection()
    return db.fetch_all("""
        SELECT t.transaction_id, t.transaction_date,
               t.total_amount,
               COUNT(ti.item_id) as items
        FROM transactions t
        LEFT JOIN transaction_items ti
               ON t.transaction_id = ti.transaction_id
        WHERE t.customer_id = %s
        GROUP BY t.transaction_id, t.transaction_date, t.total_amount
        ORDER BY t.transaction_date DESC
    """, [customer_id])


@st.cache_data(ttl=300, show_spinner=False)
def _get_total_spent(customer_id):
    db = DatabaseConnection()
    result = db.fetch_one("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM transactions WHERE customer_id = %s
    """, [customer_id])
    return float(result[0]) if result else 0.0


@st.cache_data(ttl=300, show_spinner=False)
def _get_emails(customer_id):
    db = DatabaseConnection()
    return db.fetch_all("""
        SELECT subject, sent_date, email_content
        FROM email_log
        WHERE customer_id = %s AND delivery_status = 'sent'
        ORDER BY sent_date DESC
        LIMIT 50
    """, [customer_id])


@st.cache_data(ttl=120, show_spinner=False)
def _get_new_promo_count(customer_id, last_active_date):
    """Count promotional emails sent after the customer's last active date."""
    db = DatabaseConnection()
    if not last_active_date:
        return 0

    row = db.fetch_one(
        """
        SELECT COUNT(*)
        FROM email_log
        WHERE customer_id = %s
          AND delivery_status = 'sent'
          AND email_type LIKE 'promotional%'
                    AND DATE(sent_date) >= %s
        """,
        [customer_id, last_active_date],
    )
    return int(row[0]) if row and row[0] is not None else 0


def _mark_customer_active(customer_id):
    """Persist the latest active date for customer login tracking."""
    db = DatabaseConnection()
    db.execute_query(
        """
        UPDATE customers
        SET last_active_date = CURRENT_DATE,
            updated_at = CURRENT_TIMESTAMP
        WHERE customer_id = %s
        """,
        [customer_id],
    )


def _format_promotion_subject(subject: str) -> str:
    """Convert system email subject to a cleaner customer-facing title."""
    text = (subject or "").strip()
    if text.startswith("🎉"):
        text = text[1:].strip()

    # Remove repetitive brand labels while preserving campaign details.
    text = text.replace("Sunrise Super — ", "")
    text = text.replace(" — Sunrise Super", "")
    text = " ".join(text.split())
    return text or "Special Promotion"


def _extract_promotion_window(email_content: str, sent_date) -> tuple[date | None, date | None]:
    """Extract promotion start/end dates from email content."""
    content = email_content or ""
    sent_day = sent_date.date() if hasattr(sent_date, "date") else sent_date

    window_match = re.search(
        r"valid from\s+(\d{2}\s+[A-Za-z]{3}\s+\d{4})\s+to\s+(\d{2}\s+[A-Za-z]{3}\s+\d{4})",
        content,
        flags=re.IGNORECASE,
    )
    if window_match:
        start = datetime.strptime(window_match.group(1), "%d %b %Y").date()
        end = datetime.strptime(window_match.group(2), "%d %b %Y").date()
        return start, end

    until_match = re.search(
        r"valid until\s+(\d{2}\s+[A-Za-z]{3}\s+\d{4})",
        content,
        flags=re.IGNORECASE,
    )
    if until_match:
        end = datetime.strptime(until_match.group(1), "%d %b %Y").date()
        start = sent_day if sent_day else None
        return start, end

    # Fallback for legacy emails without explicit validity range.
    if sent_day:
        return sent_day, sent_day + timedelta(days=7)
    return None, None


def _get_active_promotions(email_rows) -> list[dict]:
    today = date.today()
    promotions = []

    for row in email_rows:
        subject, sent_date, email_content = row
        start_date, end_date = _extract_promotion_window(email_content, sent_date)
        if not end_date or end_date < today:
            continue

        promotions.append({
            "subject": _format_promotion_subject(subject),
            "sent_date": sent_date,
            "start_date": start_date,
            "end_date": end_date,
        })

    return promotions


@st.cache_data(ttl=300, show_spinner=False)
def _get_favourite_products(customer_id):
    db = DatabaseConnection()
    return db.fetch_all("""
        SELECT p.product_name, p.category,
               SUM(ti.quantity) as total_qty,
               COUNT(*) as times_bought
        FROM transaction_items ti
        JOIN transactions t  ON ti.transaction_id = t.transaction_id
        JOIN product_catalog p ON ti.product_code  = p.product_code
        WHERE t.customer_id = %s
        GROUP BY p.product_name, p.category
        ORDER BY total_qty DESC
        LIMIT 10
    """, [customer_id])


@st.cache_data(ttl=300, show_spinner=False)
def _get_recommendations(customer_id):
    engine = AprioriEngine()
    return engine.get_recommendations(customer_id, top_n=6)


# ── Main dashboard ────────────────────────────────────────────────────────────
def show_customer_dashboard(customer_id):
    if not customer_id:
        st.error("No customer account linked to this login.")
        st.info("Please contact Sunrise Super staff to link your account.")
        return
# ── Refresh button ────────────────────────────────────
    col_refresh, col_settings, col_space = st.columns([1, 1, 4])
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_dashboard"):
            st.cache_data.clear()
            st.rerun()
    with col_settings:
        if st.button("⚙️ Settings", key="customer_settings"):
            st.session_state.current_page = "customer_settings"
            st.rerun()

    # Load all data in parallel (all cached)
    profile         = _get_profile(customer_id)
    purchases       = _get_purchases(customer_id)
    total_rev       = _get_total_spent(customer_id)
    emails          = _get_emails(customer_id)
    active_promos   = _get_active_promotions(emails)
    fav_products    = _get_favourite_products(customer_id)
    recommendations = _get_recommendations(customer_id)

    if not profile:
        st.error("Customer profile not found.")
        return

    # ── Unpack profile ────────────────────────────────────
    first_name   = profile[1] or "Customer"
    last_name    = profile[2] or ""
    full_name    = f"{first_name} {last_name}".strip()
    email        = profile[3]
    join_date    = profile[4]
    segment      = profile[6] or "New Customer"
    seg_color    = SEGMENT_COLORS.get(segment, '#2563EB')
    seg_friendly = SEGMENT_FRIENDLY.get(segment, '🛒 Member')
    perks        = SEGMENT_PERKS.get(segment, [])
    tx_count     = len(purchases)

    # Trigger celebration once per session if new promotional alerts are available.
    new_promo_count = _get_new_promo_count(customer_id, profile[5])
    # Fallback: if date-based comparison misses older active offers,
    # still celebrate once when active promotions exist.
    if new_promo_count == 0 and active_promos:
        new_promo_count = len(active_promos)
    promo_alert_key = f"promo_alert_seen::{customer_id}::{profile[5]}::{new_promo_count}"
    if new_promo_count > 0 and not st.session_state.get(promo_alert_key, False):
        st.balloons()
        st.success(f"🎉 You have {new_promo_count} new promotion alert(s) waiting!")
        st.session_state[promo_alert_key] = True

    active_mark_key = f"active_marked::{customer_id}"
    if not st.session_state.get(active_mark_key, False):
        _mark_customer_active(customer_id)
        st.session_state[active_mark_key] = True

    # ── Hero header ───────────────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{seg_color} 0%,{seg_color}99 100%);
                border-radius:16px;padding:28px 32px;margin-bottom:24px;">
        <div style="display:flex;align-items:center;gap:20px;">
            <div style="background:rgba(255,255,255,0.25);border-radius:50%;
                        width:68px;height:68px;display:flex;align-items:center;
                        justify-content:center;font-size:32px;flex-shrink:0;">
                🛒
            </div>
            <div>
                <div style="color:#fff;font-size:26px;font-weight:800;
                            line-height:1.2;">
                    Welcome back, {first_name}!
                </div>
                <div style="color:rgba(255,255,255,0.88);font-size:14px;
                            margin-top:6px;">
                    {seg_friendly}
                    &nbsp;·&nbsp;
                    Member since {join_date.strftime('%b %Y') if join_date else 'N/A'}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI row ───────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Purchases",  tx_count)
    with c2:
        st.metric("Total Spent",      f"Rs.{total_rev:,.0f}")
    with c3:
        avg = total_rev / tx_count if tx_count > 0 else 0
        st.metric("Avg Basket",       f"Rs.{avg:,.0f}")
    with c4:
        st.metric("Active Offers",  len(active_promos))

    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎁 My Offers",
        "🤖 Recommendations",
        "📜 Purchase History",
        "👤 My Profile",
    ])

    # ══════════════════════════════════════════════════════
    # TAB 1 — My Offers
    # ══════════════════════════════════════════════════════
    with tab1:
        st.markdown('<div class="section-title">🎁 Your Exclusive Benefits</div>',
                    unsafe_allow_html=True)

        # Membership perks card
        perks_html = "".join(
            f'<div style="padding:5px 0;font-size:14px;">✅ {p}</div>'
            for p in perks
        )
        st.markdown(
            f'<div style="background:{seg_color}12;'
            f'border:1px solid {seg_color}44;'
            f'border-radius:12px;padding:20px;margin-bottom:20px;">'
            f'<div style="font-weight:700;color:{seg_color};'
            f'font-size:16px;margin-bottom:10px;">'
            f'{seg_friendly} Benefits</div>'
            f'{perks_html}'
            f'</div>',
            unsafe_allow_html=True
        )

        # Recent promotions
        st.markdown('<div class="section-title">📧 Recent Promotions Sent to You</div>',
                    unsafe_allow_html=True)
        if active_promos:
            for promo in active_promos:
                subject = promo["subject"]
                sent_date = promo["sent_date"]
                start_date = promo["start_date"]
                end_date = promo["end_date"]
                date_str  = sent_date.strftime('%d %b %Y') if sent_date else 'N/A'
                validity = (
                    f"Valid: {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
                    if start_date and end_date else
                    "Validity available in email details"
                )
                st.markdown(
                    f'<div class="metric-card" style="margin-bottom:8px;'
                    f'padding:12px 16px;">'
                    f'<div style="font-weight:600;font-size:14px;">'
                    f'{subject}</div>'
                    f'<div style="font-size:12px;color:var(--text-muted);">'
                    f'Received: {date_str}</div>'
                    f'<div style="font-size:12px;color:var(--text-muted);">'
                    f'{validity}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(

                '<div class="alert-info">No promotions yet — '
                'check back soon for exclusive offers!</div>',

                '<div class="alert-info">No active promotions right now — '
                'check back soon for fresh offers!</div>',

                unsafe_allow_html=True
            )

    # ══════════════════════════════════════════════════════
    # TAB 2 — Recommendations (Apriori powered)
    # ══════════════════════════════════════════════════════
    with tab2:
        st.markdown('<div class="section-title">🤖 AI-Powered Recommendations</div>',
                    unsafe_allow_html=True)

        # Show which method was used
        if recommendations and recommendations[0]['confidence'] > 0:
            st.markdown(
                '<div class="alert-success" style="margin-bottom:16px;">'
                '🤖 <strong>Powered by Apriori Algorithm</strong> — '
                'recommendations based on shopping patterns of all customers.'
                '</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div class="alert-info" style="margin-bottom:16px;">'
                '📊 Showing popular products — '
                'recommendations improve as more purchases are made.'
                '</div>',
                unsafe_allow_html=True
            )

        if recommendations:
            cols = st.columns(3)
            for i, rec in enumerate(recommendations):
                unit_price  = float(rec['unit_price'])
                offer_price = float(rec['offer_price'])
                saving      = round(unit_price - offer_price, 2)
                confidence  = rec.get('confidence', 0)
                reason      = rec.get('reason', 'Popular product')

                with cols[i % 3]:
                    saving_html = (
                        f'<div style="background:#d1fae5;color:#065f46;'
                        f'border-radius:4px;padding:2px 8px;'
                        f'font-size:11px;margin-top:4px;">'
                        f'Save Rs.{saving:.2f}</div>'
                        if saving > 0 else ''
                    )
                    conf_html = (
                        f'<div style="font-size:10px;color:var(--text-muted);'
                        f'margin-top:4px;">'
                        f'🤖 {confidence*100:.0f}% match</div>'
                        if confidence > 0 else
                        f'<div style="font-size:10px;color:var(--text-muted);'
                        f'margin-top:4px;">⭐ {reason}</div>'
                    )
                    st.markdown(
                        f'<div class="metric-card" style="text-align:center;'
                        f'padding:16px;margin-bottom:12px;">'
                        f'<div style="font-size:26px;margin-bottom:8px;">🛒</div>'
                        f'<div style="font-weight:700;font-size:13px;'
                        f'margin-bottom:3px;">{rec["product_name"]}</div>'
                        f'<div style="font-size:11px;color:var(--text-muted);'
                        f'margin-bottom:8px;">{rec["category"]}</div>'
                        f'<div style="text-decoration:line-through;'
                        f'color:var(--text-muted);font-size:12px;">'
                        f'Rs.{unit_price:.2f}</div>'
                        f'<div style="color:#059669;font-weight:800;'
                        f'font-size:16px;">Rs.{offer_price:.2f}</div>'
                        f'{saving_html}{conf_html}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
        else:
            st.markdown(
                '<div class="alert-info">Make your first purchase to get '
                'personalised recommendations!</div>',
                unsafe_allow_html=True
            )

        # Favourite products chart
        if fav_products:
            st.markdown("---")
            st.markdown('<div class="section-title">❤️ Your Most Bought Products</div>',
                        unsafe_allow_html=True)
            df_p = pd.DataFrame(
                fav_products,
                columns=['Product', 'Category', 'Total Qty', 'Times Bought']
            )
            fig = px.bar(
                df_p, x='Product', y='Times Bought',
                color='Category',
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig.update_layout(
                height=300,
                margin=dict(t=20, b=20),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True,
                            config={"displaylogo": False})

    # ══════════════════════════════════════════════════════
    # TAB 3 — Purchase History
    # ══════════════════════════════════════════════════════
    with tab3:
        st.markdown('<div class="section-title">📜 Your Purchase History</div>',
                    unsafe_allow_html=True)

        if purchases:
            df_purchases = pd.DataFrame(
                purchases,
                columns=['ID', 'Date', 'Amount', 'Items']
            )
            df_purchases['Amount'] = df_purchases['Amount'].apply(float)

            # Spending over time chart
            fig2 = px.line(
                df_purchases.sort_values('Date'),
                x='Date', y='Amount',
                color_discrete_sequence=['#2563EB'],
                title='Your Spending Over Time',
                markers=True
            )
            fig2.update_layout(
                height=280,
                margin=dict(t=40, b=20),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig2, use_container_width=True,
                            config={"displaylogo": False})

            # Table
            df_display = df_purchases.copy()
            df_display['Amount'] = df_display['Amount'].apply(
                lambda x: f"Rs.{x:,.2f}"
            )
            df_display['Date'] = pd.to_datetime(
                df_display['Date']
            ).dt.strftime('%d %b %Y')
            st.dataframe(
                df_display[['ID', 'Date', 'Amount', 'Items']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.markdown(
                '<div class="alert-info">No purchases yet. '
                'Visit Sunrise Super to get started!</div>',
                unsafe_allow_html=True
            )

    # ══════════════════════════════════════════════════════
    # TAB 4 — My Profile
    # ══════════════════════════════════════════════════════
    with tab4:
        st.markdown('<div class="section-title">👤 My Profile</div>',
                    unsafe_allow_html=True)

        col_info, col_tier = st.columns(2)

        with col_info:
            st.markdown(
                f'<div class="metric-card">'
                f'<div style="font-weight:700;font-size:15px;'
                f'margin-bottom:14px;">Account Details</div>'
                f'<div style="font-size:14px;line-height:2.2;">'
                f'👤 <strong>{full_name}</strong><br>'
                f'📧 {email}<br>'
                f'🆔 {customer_id}<br>'
                f'📅 Member since '
                f'{join_date.strftime("%d %b %Y") if join_date else "N/A"}'
                f'</div></div>',
                unsafe_allow_html=True
            )

        with col_tier:
            st.markdown(
                f'<div class="metric-card" '
                f'style="border-top:4px solid {seg_color};">'
                f'<div style="font-weight:700;font-size:15px;'
                f'margin-bottom:14px;">Membership Tier</div>'
                f'<div style="font-size:24px;font-weight:800;'
                f'color:{seg_color};">{seg_friendly}</div>'
                f'<div style="font-size:13px;color:var(--text-muted);'
                f'margin-top:10px;line-height:1.8;">'
                f'Total spent: <strong>Rs.{total_rev:,.2f}</strong><br>'
                f'Purchases: <strong>{tx_count}</strong></div>'
                f'</div>',
                unsafe_allow_html=True
            )

        # Tier progress bars
        st.markdown("---")
        st.markdown('<div class="section-title">📈 Membership Tier Progress</div>',
                    unsafe_allow_html=True)

        tiers = [
            ("🆕 New Member",      0,     '#0891B2'),
            ("🛍️ Special Member",  1000,  '#2563EB'),
            ("🛒 Loyal Member",    5000,  '#059669'),
            ("💎 Premium Member",  15000, '#7C3AED'),
            ("⭐ VIP Member",      10000, '#d4ac0d'),
        ]

        for tier_name, threshold, color in tiers:
            if threshold == 0:
                pct     = 100
                reached = True
            else:
                pct     = min(100, int((total_rev / threshold) * 100))
                reached = total_rev >= threshold

            st.markdown(
                f'<div style="margin-bottom:12px;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:13px;margin-bottom:5px;">'
                f'<span style="color:{"#059669" if reached else "var(--text-muted)"};">'
                f'{"✅" if reached else "🔒"} {tier_name}</span>'
                f'<span style="color:var(--text-muted);">'
                f'Rs.{threshold:,}</span>'
                f'</div>'
                f'<div style="background:#e0e0e0;border-radius:6px;height:8px;">'
                f'<div style="background:{color};width:{pct}%;height:8px;'
                f'border-radius:6px;"></div>'
                f'</div></div>',
                unsafe_allow_html=True
            )

    # ── Footer ────────────────────────────────────────────
    st.markdown(
        '<div class="footer">Sunrise Super · Kundasale, Sri Lanka · '
        'Smart Loyalty & Rewards</div>',
        unsafe_allow_html=True
    )
