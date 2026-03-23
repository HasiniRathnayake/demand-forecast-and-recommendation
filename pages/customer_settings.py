import streamlit as st
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.db_connection import DatabaseConnection


def _load_customer_preferences(customer_id):
    db = DatabaseConnection()
    return db.fetch_one(
        """
        SELECT first_name, email_notification_enabled, promotional_emails_allowed
        FROM customers
        WHERE customer_id = %s
        """,
        [customer_id],
    )


def _save_customer_preferences(customer_id, email_enabled, promo_allowed):
    db = DatabaseConnection()
    return db.execute_query(
        """
        UPDATE customers
        SET email_notification_enabled = %s,
            promotional_emails_allowed = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE customer_id = %s
        """,
        [email_enabled, promo_allowed, customer_id],
    )


def show_customer_settings(customer_id):
    st.markdown('<p class="main-header">⚙️ Promotion Preferences</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Choose which promotion emails you want to receive.</p>',
        unsafe_allow_html=True,
    )

    if not customer_id:
        st.error("No customer account linked to this login.")
        return

    row = _load_customer_preferences(customer_id)
    if not row:
        st.error("Customer profile not found.")
        return

    first_name, email_enabled, promo_allowed = row
    st.markdown(
        f"<div class='alert-info'>Hi <strong>{first_name or 'Customer'}</strong>, update your email preferences below.</div>",
        unsafe_allow_html=True,
    )

    new_email_enabled = st.toggle(
        "Receive account emails",
        value=bool(email_enabled),
        help="Turn off if you do not want any email notifications.",
    )

    new_promo_allowed = st.toggle(
        "Receive promotional offers",
        value=bool(promo_allowed),
        disabled=not new_email_enabled,
        help="Turn off to stop marketing and discount emails.",
    )

    if not new_email_enabled and new_promo_allowed:
        new_promo_allowed = False

    if st.button("Save Preferences", type="primary", use_container_width=True):
        ok = _save_customer_preferences(customer_id, new_email_enabled, new_promo_allowed)
        if ok:
            st.success("✅ Preferences updated successfully.")
            st.cache_data.clear()
        else:
            st.error("❌ Could not update preferences. Please try again.")

    st.markdown("---")
    st.caption("Tip: If promotional offers are off, you will not receive future promotion emails.")
