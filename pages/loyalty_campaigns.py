# pages/loyalty_campaigns.py
import streamlit as st
import sys, os
import re
import streamlit.components.v1 as components
import plotly.express as px
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection
from scripts.offers_engine import OffersEngine
from scripts.email_sender import EmailSender
import pandas as pd
from datetime import date, timedelta

# ── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = {
    "🌸 Seasonal Campaign": {
        "color": "#f39c12",
        "description": "Perfect for Avurudu, Christmas, New Year, Vesak",
        "suggested_discount": 15,
        "target_segments": ["VIP Customer", "High Value", "Regular Customer",
                            "Occasional", "New Customer"],
        "default_message": "Wishing you and your family a joyful season! "
                           "As a valued customer, we have prepared something special just for you.",
    },
    "⚡ Flash Sale": {
        "color": "#e74c3c",
        "description": "Limited time urgent discount to drive quick purchases",
        "suggested_discount": 20,
        "target_segments": ["Regular Customer", "Occasional", "New Customer"],
        "default_message": "Hurry! This exclusive deal is only available for a limited time. "
                           "Stock up on your favourites before it's gone!",
    },
    "💝 Win-Back Campaign": {
        "color": "#8e44ad",
        "description": "Re-engage customers who have not shopped recently",
        "suggested_discount": 30,
        "target_segments": ["At Risk", "Churned"],
        "default_message": "It has been a while since we have seen you! "
                           "We miss having you at Sunrise Super. "
                           "Come back and enjoy an exclusive discount just for you.",
    },
    "⭐ VIP Exclusive": {
        "color": "#d4ac0d",
        "description": "Premium offer exclusively for top spending customers",
        "suggested_discount": 20,
        "target_segments": ["VIP Customer", "High Value"],
        "default_message": "As one of our most valued customers, you deserve the very best. "
                           "This exclusive offer is available only to our VIP members.",
    },
    "🆕 New Arrivals": {
        "color": "#27ae60",
        "description": "Announce new products with an introductory offer",
        "suggested_discount": 10,
        "target_segments": ["VIP Customer", "High Value", "Regular Customer",
                            "Occasional", "New Customer"],
        "default_message": "Exciting news! We have just added new products to our shelves. "
                           "Be the first to try them with an exclusive introductory discount.",
    },
}

# ── Friendly segment names for email preview 
FRIENDLY_SEGMENT = {
    'VIP Customer':     'VIP Member',
    'High Value':       'Valued Member',
    'Regular Customer': 'Loyal Member',
    'At Risk':          'Valued Member',
    'Occasional':       'Special Member',
    'New Customer':     'New Member',
    'Churned':          'Valued Member',
}

PREFERENCE_MESSAGE_SNIPPETS = {
    '🐟 Fresh & Protein Lovers': (
        "Because you often choose fresh proteins, we selected strong value deals on seafood,"
        " dairy, and daily essentials for your next basket."
    ),
    '🥦 Balanced Shoppers': (
        "Your balanced shopping style inspired this mix of healthy staples, household must-haves,"
        " and weekly-value picks."
    ),
    '👶 Family & Baby Care': (
        "We focused this campaign on family-friendly bundles and baby-care essentials to help"
        " you save more on routine purchases."
    ),
    '🥤 Drink & Health Focused': (
        "Since you prefer drinks and wellness products, we highlighted offers on beverages,"
        " nutrition, and health-focused categories."
    ),
}

CANONICAL_TASTE_LABELS = {
    "balanced shoppers": "🥦 Balanced Shoppers",
    "fresh & protein lovers": "🐟 Fresh & Protein Lovers",
    "family & baby care": "👶 Family & Baby Care",
    "drink & health focused": "🥤 Drink & Health Focused",
}


def _normalize_taste_label(raw_value: str | None) -> str:
    text = re.sub(r"\s+", " ", (raw_value or "").strip())
    if not text:
        return "Unknown"

    # Remove leading emoji/symbols then normalize matching by lowercase text.
    text_no_emoji = re.sub(r"^[^\w]+\s*", "", text)
    key = text_no_emoji.lower()
    return CANONICAL_TASTE_LABELS.get(key, text)


def _compose_campaign_message(base_message, taste_preference, personalize):
    text = (base_message or '').strip()
    if not personalize:
        return text

    snippet = PREFERENCE_MESSAGE_SNIPPETS.get((taste_preference or '').strip())
    if not snippet:
        return text
    return f"{text}\n\n{snippet}" if text else snippet


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


# ── Cached DB calls — only hit database once per 5 minutes ───────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _load_segments():
    db = DatabaseConnection()
    segment_col = _assignment_segment_column()
    return db.fetch_all(f"""
        SELECT cs.segment_name, COUNT(csa.customer_id) as count
        FROM customer_segments cs
        LEFT JOIN customer_segment_assignment csa
               ON cs.segment_id = csa.{segment_col}
        GROUP BY cs.segment_name
        HAVING COUNT(csa.customer_id) > 0
        ORDER BY count DESC
    """)


@st.cache_data(ttl=120, show_spinner=False)
def _load_taste_preferences(selected_segs_tuple):
    db = DatabaseConnection()
    segment_col = _assignment_segment_column()
    taste_col = _assignment_taste_column()

    if not selected_segs_tuple or not taste_col:
        return []

    seg_placeholders = ','.join(['%s'] * len(selected_segs_tuple))
    rows = db.fetch_all(f"""
                SELECT COALESCE(NULLIF(REGEXP_REPLACE(TRIM(csa.{taste_col}::text), '\\s+', ' ', 'g'), ''), 'Unknown') AS taste_pref,
               COUNT(DISTINCT c.customer_id) as customer_count
        FROM customers c
        JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
        JOIN customer_segments cs ON csa.{segment_col} = cs.segment_id
        WHERE c.is_active = TRUE
          AND cs.segment_name IN ({seg_placeholders})
          AND csa.{taste_col} IS NOT NULL
          AND TRIM(csa.{taste_col}::text) <> ''
                GROUP BY taste_pref
        ORDER BY customer_count DESC, taste_pref
    """, list(selected_segs_tuple))

    deduped_counts = {}
    for taste_pref, customer_count in rows:
        canonical = _normalize_taste_label(taste_pref)
        deduped_counts[canonical] = deduped_counts.get(canonical, 0) + int(customer_count or 0)

    return sorted(deduped_counts.items(), key=lambda x: (-x[1], x[0]))


@st.cache_data(ttl=120, show_spinner=False)
def _load_segment_taste_matrix(selected_segs_tuple):
    db = DatabaseConnection()
    segment_col = _assignment_segment_column()
    taste_col = _assignment_taste_column()

    if not selected_segs_tuple:
        return pd.DataFrame(columns=["segment_name", "taste_preference", "customer_count"])

    seg_placeholders = ','.join(['%s'] * len(selected_segs_tuple))

    if taste_col:
        taste_expr = f"COALESCE(NULLIF(REGEXP_REPLACE(TRIM(csa.{taste_col}::text), '\\s+', ' ', 'g'), ''), 'Unknown')"
    else:
        taste_expr = "'Unknown'"

    rows = db.fetch_all(f"""
        SELECT
            cs.segment_name,
            {taste_expr} AS taste_preference,
            COUNT(DISTINCT c.customer_id) AS customer_count
        FROM customers c
        JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
        JOIN customer_segments cs ON csa.{segment_col} = cs.segment_id
        WHERE c.is_active = TRUE
          AND cs.segment_name IN ({seg_placeholders})
        GROUP BY cs.segment_name, taste_preference
        ORDER BY cs.segment_name, customer_count DESC
    """, list(selected_segs_tuple))

    matrix_df = pd.DataFrame(rows, columns=["segment_name", "taste_preference", "customer_count"])
    if matrix_df.empty:
        return matrix_df

    matrix_df["taste_preference"] = matrix_df["taste_preference"].apply(_normalize_taste_label)
    matrix_df = (
        matrix_df.groupby(["segment_name", "taste_preference"], as_index=False)["customer_count"]
        .sum()
    )
    return matrix_df


@st.cache_data(ttl=120, show_spinner=False)
def _load_eligible(selected_segs_tuple, selected_tastes_tuple):
    db = DatabaseConnection()
    segment_col = _assignment_segment_column()
    taste_col = _assignment_taste_column()

    seg_placeholders = ','.join(['%s'] * len(selected_segs_tuple))

    if taste_col:
        taste_expr = f"COALESCE(NULLIF(REGEXP_REPLACE(TRIM(csa.{taste_col}::text), '\\s+', ' ', 'g'), ''), 'Unknown')"
        taste_select = f"{taste_expr} as taste_preference"
        taste_group = ""
    else:
        taste_expr = "'Unknown'"
        taste_select = "'Unknown' as taste_preference"
        taste_group = ""

    where_clause = [f"cs.segment_name IN ({seg_placeholders})", "c.is_active = TRUE"]
    params = list(selected_segs_tuple)

    rows = db.fetch_all(f"""
        SELECT c.customer_id, c.first_name, c.email,
               cs.segment_name,
               c.email_notification_enabled,
               c.promotional_emails_allowed,
               COALESCE(SUM(t.total_amount), 0) as total_spent,
               {taste_select}
        FROM customers c
        JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
        JOIN customer_segments cs ON csa.{segment_col} = cs.segment_id
        LEFT JOIN transactions t ON c.customer_id = t.customer_id
        WHERE {' AND '.join(where_clause)}
        GROUP BY c.customer_id, c.first_name, c.email,
                 cs.segment_name, c.email_notification_enabled,
                 c.promotional_emails_allowed, {taste_expr}
        ORDER BY total_spent DESC
    """, params)

    normalized_rows = []
    for row in rows:
        mutable = list(row)
        if len(mutable) > 7:
            mutable[7] = _normalize_taste_label(mutable[7])
        normalized_rows.append(tuple(mutable))

    if selected_tastes_tuple:
        selected_set = set(selected_tastes_tuple)
        normalized_rows = [r for r in normalized_rows if len(r) > 7 and r[7] in selected_set]

    return normalized_rows


def _build_preview(tmpl, campaign_name, custom_message,
                   discount_pct, promo_start, valid_until, sample_name, sample_seg):
    """Build the HTML email preview string."""
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:8px;background:#f0f0f0;">
<div style="max-width:420px;margin:auto;font-family:Arial,sans-serif;
            border-radius:14px;overflow:hidden;
            box-shadow:0 4px 20px rgba(0,0,0,0.12);">

  <div style="background:{tmpl['color']};padding:20px;text-align:center;">
    <div style="font-size:26px;">🛒</div>
    <div style="color:#fff;font-size:18px;font-weight:800;
                letter-spacing:1px;margin-top:4px;">SUNRISE SUPER</div>
    <div style="color:rgba(255,255,255,0.85);font-size:10px;
                letter-spacing:2px;margin-top:3px;text-transform:uppercase;">
      {campaign_name}
    </div>
  </div>

  <div style="padding:20px;background:#fff;">
    <h2 style="color:#2c3e50;margin:0 0 3px;font-size:16px;">
      Hi {sample_name}! 👋
    </h2>
    <p style="color:#aaa;font-size:10px;margin:0 0 12px;">{sample_seg}</p>
    <p style="color:#555;line-height:1.6;margin:0 0 16px;font-size:12px;">
      {custom_message}
    </p>

    <div style="background:{tmpl['color']}18;
                border:2px dashed {tmpl['color']};
                border-radius:10px;padding:16px;text-align:center;">
      <div style="font-size:36px;font-weight:800;color:{tmpl['color']};">
        {discount_pct}% OFF
      </div>
      <div style="color:#888;font-size:11px;margin-top:5px;">
                Valid from {promo_start.strftime('%d %b %Y')} to {valid_until.strftime('%d %b %Y')}
        &nbsp;·&nbsp; In-store &amp; online
      </div>
    </div>

    <div style="text-align:center;margin-top:16px;">
      <div style="background:{tmpl['color']};color:#fff;
                   padding:9px 24px;border-radius:7px;
                   font-weight:700;font-size:13px;display:inline-block;">
        Shop Now →
      </div>
    </div>
  </div>

  <div style="background:#f8f9fa;padding:12px;text-align:center;
              border-top:1px solid #eee;">
    <p style="color:#aaa;font-size:9px;margin:0;">
      Sunrise Super · Kundasale, Sri Lanka<br>
      You are receiving this as a loyalty member.
    </p>
  </div>
</div>
</body></html>"""


# ── Main page ─────────────────────────────────────────────────────────────────
def show_promotions():

    st.title("🎯 Campaign Builder")
    st.markdown("Create and send personalised email campaigns to your customers.")
    st.divider()

    # Load segments once (cached)
    seg_data = _load_segments()
    if not seg_data:
        st.warning("No segments found. Go to Customer Segments and sync cluster segments first.")
        return

    seg_options = {row[0]: row[1] for row in seg_data}

    # ── TWO COLUMN LAYOUT — controls left, preview right ─────────────────────
    col_controls, col_preview = st.columns([1, 1])

    with col_controls:
        # ── Step 1: Template ──────────────────────────────
        st.markdown("#### Step 1 — Choose a Template")
        template_name = st.selectbox(
            "Template", list(TEMPLATES.keys()),
            label_visibility="collapsed"
        )
        tmpl = TEMPLATES[template_name]
        st.markdown(
            f'<div style="background:{tmpl["color"]}15;'
            f'border-left:3px solid {tmpl["color"]}; '
            f'padding:8px 14px;border-radius:0 6px 6px 0;'
            f'font-size:12px;color:#555;margin-bottom:8px;">'
            f'{tmpl["description"]}</div>',
            unsafe_allow_html=True
        )

        st.markdown("---")

        # ── Step 2: Campaign Details ──────────────────────
        st.markdown("#### Step 2 — Campaign Details")

        campaign_name = st.text_input(
            "Campaign Name",
            value=f"Sunrise Super — {template_name.split(' ', 1)[1]}"
        )
        discount_pct = st.number_input(
            "Discount %",
            min_value=1, max_value=90,
            value=tmpl['suggested_discount'],
            step=1,
            help="Type any number"
        )

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            send_date = st.date_input(
                "Send Date",
                value=date.today(),
                min_value=date.today()
            )
        with col_d2:
            promo_start = st.date_input(
                "Promotion Starts",
                value=send_date,
                min_value=send_date,
            )

        valid_days = st.number_input(
            "Valid (days)",
            min_value=1, max_value=30,
            value=7
        )

        valid_until = promo_start + timedelta(days=int(valid_days))

        custom_message = st.text_area(
            "Email Message",
            value=tmpl['default_message'],
            height=90,
            help="This appears in the email body — edit freely"
        )

        st.markdown("---")

        # ── Step 3: Target Audience ───────────────────────
        st.markdown("#### Step 3 — Target Audience")

        default_segs  = [s for s in tmpl['target_segments'] if s in seg_options]
        selected_segs = st.multiselect(
            "Select Segments",
            options=list(seg_options.keys()),
            default=default_segs,
            format_func=lambda x: f"{x} ({seg_options[x]} customers)"
        )

        if not selected_segs:
            st.info("Select at least one segment.")
            col_preview.markdown("#### 📩 Live Preview")
            col_preview.info("Select a segment to see the preview.")
            return

        matrix_df = _load_segment_taste_matrix(tuple(selected_segs))
        if not matrix_df.empty:
            st.markdown("##### Audience Opportunity Matrix")
            st.caption("Rows: RFM segments · Columns: taste clusters · Cells: active customer count")

            matrix = matrix_df.pivot_table(
                index="segment_name",
                columns="taste_preference",
                values="customer_count",
                aggfunc="sum",
                fill_value=0,
            )

            row_order = [seg for seg in selected_segs if seg in matrix.index]
            if row_order:
                matrix = matrix.reindex(row_order)

            col_order = matrix.sum(axis=0).sort_values(ascending=False).index.tolist()
            matrix = matrix[col_order]

            fig = px.imshow(
                matrix,
                text_auto=True,
                aspect="auto",
                color_continuous_scale="Blues",
                labels={"x": "Taste Cluster", "y": "RFM Segment", "color": "Customers"},
            )
            fig.update_layout(
                height=max(300, 140 + 40 * len(matrix.index)),
                margin=dict(l=10, r=10, t=10, b=10),
                coloraxis_colorbar=dict(title="Customers"),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            top_pair = matrix.stack().idxmax() if not matrix.empty else None
            top_count = int(matrix.max().max()) if not matrix.empty else 0
            if top_pair and top_count > 0:
                top_segment, top_taste = top_pair
                st.info(
                    f"Biggest opportunity: {top_count} customers in '{top_segment}' × '{top_taste}'. "
                    "Use this overlap to shape your campaign product and message."
                )
        else:
            st.info("No segment-taste overlap data available yet for the selected segments.")

        taste_pref_rows = _load_taste_preferences(tuple(selected_segs))
        if taste_pref_rows:
            taste_options = {row[0]: row[1] for row in taste_pref_rows}
            selected_tastes = st.multiselect(
                "Filter by Product Preference (Optional)",
                options=list(taste_options.keys()),
                format_func=lambda x: f"{x} ({taste_options[x]} customers)",
                help="Use this to target taste clusters like Fresh & Protein Lovers."
            )
        else:
            selected_tastes = []

        personalize_by_preference = st.toggle(
            "Personalize Email Message By Product Preference",
            value=True,
            help="Adds a tailored message paragraph based on each customer's taste profile."
        )

        # Load eligible customers (cached)
        eligible_rows  = _load_eligible(tuple(selected_segs), tuple(selected_tastes))
        total_selected = len(eligible_rows)
        email_eligible = sum(1 for r in eligible_rows if r[4] and r[5])

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric("Selected", total_selected)
        with col_m2:
            st.metric("Will Receive Email", email_eligible)

        with st.expander(f"👥 View {total_selected} customers"):
            if eligible_rows:
                df_e = pd.DataFrame(
                    eligible_rows,
                    columns=['ID', 'Name', 'Email', 'Segment',
                             'Email On', 'Promo OK', 'Spent', 'Preference']
                )
                df_e['Email On'] = df_e['Email On'].apply(lambda x: '✅' if x else '❌')
                df_e['Promo OK'] = df_e['Promo OK'].apply(lambda x: '✅' if x else '❌')
                df_e['Spent']    = df_e['Spent'].apply(
                    lambda x: f"Rs.{float(x):,.2f}"
                )
                st.dataframe(df_e, use_container_width=True, hide_index=True)

        st.markdown("---")


    # ── RIGHT COLUMN: Live Preview + Send ────────────────────────────────────
    with col_preview:
        st.markdown("#### 📩 Live Preview")
        st.caption("Updates as you change settings on the left")

        # Use first eligible customer if available, else placeholder
        if 'eligible_rows' in dir() and eligible_rows:
            sample_name = str(eligible_rows[0][1]) or "Valued Customer"
            raw_seg     = str(eligible_rows[0][3]) or "Member"
            sample_pref = str(eligible_rows[0][7]) if len(eligible_rows[0]) > 7 else ""
        else:
            sample_name = "Valued Customer"
            raw_seg     = selected_segs[0] if selected_segs else "Member"
            sample_pref = ""

        sample_seg = FRIENDLY_SEGMENT.get(raw_seg, 'Loyalty Member')
        preview_message = _compose_campaign_message(
            custom_message,
            sample_pref,
            personalize_by_preference
        )

        preview = _build_preview(
            tmpl           = tmpl,
            campaign_name  = campaign_name,
            custom_message = preview_message,
            discount_pct   = discount_pct,
            promo_start    = promo_start,
            valid_until    = valid_until,
            sample_name    = sample_name,
            sample_seg     = sample_seg,
        )
        components.html(preview, height=500, scrolling=False)

        st.markdown("---")

        # ── Step 4: Send (below preview) ─────────────────
        if 'eligible_rows' in dir() and eligible_rows:
            st.markdown("#### Step 4 — Send Campaign")

            sender = EmailSender()
            if st.button("⚙️ Process Due Scheduled Emails", use_container_width=True):
                due_summary = sender.process_due_scheduled_emails()
                if due_summary['total_due'] == 0:
                    st.info("No scheduled emails are due yet.")
                else:
                    st.success(
                        f"Processed {due_summary['total_due']} due emails: "
                        f"{due_summary['sent']} sent, {due_summary['failed']} failed"
                    )
                    if due_summary['results']:
                        st.dataframe(
                            pd.DataFrame(due_summary['results']),
                            use_container_width=True,
                            hide_index=True,
                        )

            st.caption("Use this button to verify scheduled delivery without waiting for app restarts.")

            st.markdown(
                f'<div style="background:#f8f9fa;border:1px solid #e0e0e0;'
                f'border-radius:8px;padding:12px 16px;font-size:13px;'
                f'line-height:1.9;margin-bottom:12px;">'
                f'📋 <strong>{campaign_name}</strong><br>'
                f'🎯 <strong>{discount_pct}% OFF</strong><br>'
                f'👥 <strong>{email_eligible}</strong> customers<br>'
                f'📅 Send date <strong>{send_date.strftime("%d %b %Y")}</strong><br>'
                f'🛍️ Promotion <strong>{promo_start.strftime("%d %b %Y")}</strong> '
                f'to <strong>{valid_until.strftime("%d %b %Y")}</strong>'
                f'</div>',
                unsafe_allow_html=True
            )

            test_mode = st.toggle(
                "🧪 Test Mode",
                value=True,
                help="ON = sends to your Gmail only"
            )

            if test_mode:
                st.markdown(
                    '<div class="alert-info" style="margin:6px 0;font-size:12px;">'
                    '🧪 Test Mode ON — sends to your Gmail only</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="alert-warning" style="margin:6px 0;font-size:12px;">'
                    f'🚀 Live Mode — sends to {email_eligible} real customers!</div>',
                    unsafe_allow_html=True
                )

            # ── VALIDATION BEFORE SEND ──────────────────────────────────
            validation_errors = []
            
            # Campaign name validation
            if not campaign_name or len(campaign_name.strip()) < 3:
                validation_errors.append("❌ Campaign name must be at least 3 characters")
            if len(campaign_name) > 100:
                validation_errors.append("❌ Campaign name cannot exceed 100 characters")
            
            # Message validation
            if not custom_message or len(custom_message.strip()) < 10:
                validation_errors.append("❌ Email message must be at least 10 characters")
            if len(custom_message) > 500:
                validation_errors.append("❌ Email message cannot exceed 500 characters")
            
            # Discount validation
            if discount_pct < 1 or discount_pct > 90:
                validation_errors.append("❌ Discount must be between 1% and 90%")
            if discount_pct > 50:
                validation_errors.append("⚠️ Warning: Discount over 50% may impact profitability")
            
            # Date validation
            max_future_days = 90
            days_ahead = (send_date - date.today()).days
            if days_ahead > max_future_days:
                validation_errors.append(f"❌ Send date cannot be more than {max_future_days} days in advance")
            if promo_start < send_date:
                validation_errors.append("❌ Promotion start date cannot be earlier than send date")
            
            # Valid days validation
            if valid_days < 1:
                validation_errors.append("❌ Offer must be valid for at least 1 day")
            if valid_days > 60:
                validation_errors.append("⚠️ Warning: Offer valid for over 60 days may reduce urgency")
            
            # Audience validation
            if not selected_segs or len(selected_segs) == 0:
                validation_errors.append("❌ Select at least one customer segment")
            if email_eligible == 0:
                validation_errors.append("❌ No eligible customers for selected segment/preference filters")
            
            # Display validation errors
            if validation_errors:
                error_container = st.container(border=True)
                error_container.markdown("### 🔍 Validation Issues")
                for error in validation_errors:
                    error_container.markdown(error)
            
            # Disable send button if errors exist
            send_enabled = len(validation_errors) == 0
            
            scheduled = send_date > date.today()
            btn_label = (
                f"📅 Schedule for {send_date.strftime('%d %b %Y')}"
                if scheduled else "📧 Send Campaign Now"
            )

            if st.button(btn_label, type="primary", use_container_width=True, disabled=not send_enabled):
                customers_list = [{
                    'customer_id':   r[0],
                    'first_name':    r[1],
                    'email':         r[2],
                    'segment':       r[3],
                    'email_enabled': r[4],
                    'promo_allowed': r[5],
                    'total_spent':   float(r[6]),
                    'taste_preference': r[7] if len(r) > 7 else None,
                    'tx_count':      1,
                    'avg_basket':    0,
                    'days_inactive': 0
                } for r in eligible_rows]

                engine = OffersEngine()
                offers = engine.generate_all_offers(customers_list)
                preference_by_customer = {
                    c['customer_id']: c.get('taste_preference')
                    for c in customers_list
                }

                for o in offers:
                    taste_pref = preference_by_customer.get(o['customer_id'])
                    o['discount_pct'] = discount_pct
                    o['offer_text']   = f"{discount_pct}% OFF — {campaign_name}"
                    o['promo_start']  = promo_start.strftime('%d %b %Y')
                    o['promo_end']    = valid_until.strftime('%d %b %Y')
                    o['taste_preference'] = taste_pref
                    o['campaign_message'] = _compose_campaign_message(
                        custom_message,
                        taste_pref,
                        personalize_by_preference
                    )

                if scheduled:
                    queue_summary = sender.queue_scheduled_emails(
                        offers=offers,
                        send_date=send_date,
                        test_mode=test_mode,
                    )
                    st.success(
                        f"✅ **{campaign_name}** scheduled for "
                        f"**{send_date.strftime('%d %b %Y')}** "
                        f"— queued: {queue_summary['queued']}, "
                        f"skipped: {queue_summary['skipped']}, "
                        f"failed: {queue_summary['failed']}"
                    )
                    if queue_summary['results']:
                        st.dataframe(
                            pd.DataFrame(queue_summary['results']),
                            use_container_width=True,
                            hide_index=True,
                        )
                    st.cache_data.clear()
                else:
                    progress = st.progress(0, text="Preparing...")
                    progress.progress(30, text="Generating offers...")

                    progress.progress(65, text="Sending emails...")
                    summary = sender.send_promotional_emails(
                        offers, test_mode=test_mode
                    )
                    progress.progress(100, text="Done!")

                    c1, c2, c3 = st.columns(3)
                    c1.metric("✅ Sent",    summary['sent'])
                    c2.metric("⏭️ Skipped", summary['skipped'])
                    c3.metric("❌ Failed",  summary['failed'])

                    if summary['sent'] > 0:
                        st.success(f"🎉 **{campaign_name}** sent!")
                        st.cache_data.clear()
                    elif summary['skipped'] == len(offers):
                        st.markdown(
                            '<div class="alert-warning">'
                            'All customers skipped — email notifications disabled.'
                            '</div>',
                            unsafe_allow_html=True
                        )
                    if summary['results']:
                        st.dataframe(
                            pd.DataFrame(summary['results']),
                            use_container_width=True,
                            hide_index=True
                        )