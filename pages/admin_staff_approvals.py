from __future__ import annotations

import streamlit as st

from services.auth_service import (
    fetch_staff_approval_history,
    fetch_pending_staff_approvals,
    get_current_user,
    require_auth,
    review_staff_approval,
)
from ui.styles import inject_styles, render_page_heading


def render_admin_staff_approvals() -> None:
    inject_styles()
    require_auth(["admin"])

    current_user = get_current_user() or {}
    reviewer = current_user.get("username", "admin")

    render_page_heading("Staff Approval Center")
    st.markdown("---")

    try:
        pending = fetch_pending_staff_approvals()
        history = fetch_staff_approval_history(limit=300)
    except Exception as exc:
        st.error(
            "Unable to load staff approvals. Make sure setup_staff_approvals.sql is applied. "
            f"Details: {exc}"
        )
        return

    tab_pending, tab_history = st.tabs(["Pending Requests", "Approval History"])

    with tab_pending:
        if not pending:
            st.success("No pending staff approvals.")
        else:
            st.info(f"Pending requests: {len(pending)}")

            for row in pending:
                uid = row.get("user_id")
                username = row.get("username", "unknown")
                email = row.get("email", "")

                with st.container(border=True):
                    c1, c2, c3 = st.columns([5, 1, 1])
                    with c1:
                        st.markdown(f"**{username}**  ")
                        st.caption(f"User ID: {uid} | Email: {email}")
                        st.caption(
                            f"Registered: {row.get('created_at') or '-'} | Requested: {row.get('requested_at') or '-'}"
                        )
                    with c2:
                        if st.button("Approve", key=f"approve_staff_{uid}", type="primary", use_container_width=True):
                            ok, msg = review_staff_approval(uid, approve=True, reviewed_by=reviewer)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            st.error(msg)
                    with c3:
                        if st.button("Reject", key=f"reject_staff_{uid}", use_container_width=True):
                            ok, msg = review_staff_approval(uid, approve=False, reviewed_by=reviewer)
                            if ok:
                                st.warning(msg)
                                st.rerun()
                            st.error(msg)

    with tab_history:
        if not history:
            st.info("No approved or rejected requests yet.")
            return

        st.caption("Latest approvals and rejections")
        history_rows = []
        for row in history:
            status = (row.get("approval_status") or "").upper()
            history_rows.append(
                {
                    "User ID": row.get("user_id"),
                    "Username": row.get("username", "unknown"),
                    "Email": row.get("email", ""),
                    "Status": status,
                    "Reviewed By": row.get("reviewed_by") or "-",
                    "Reviewed At": row.get("reviewed_at") or "-",
                    "Requested At": row.get("requested_at") or "-",
                }
            )
        st.dataframe(history_rows, use_container_width=True, hide_index=True)
