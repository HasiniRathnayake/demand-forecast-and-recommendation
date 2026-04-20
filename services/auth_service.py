"""
services/auth_service.py
=========================
Handles user authentication, registration, and session management.
Uses bcrypt for password hashing — never stores plain text passwords.

Roles:
  staff    → access to all dashboards (demand forecast, replenishment, etc.)
  customer → access to customer loyalty dashboard only
  admin    → full access + user management
    supplier → access to supplier order dashboard only
"""

from __future__ import annotations
import bcrypt
import re
import streamlit as st
from datetime import datetime
from data.db_client import get_client


APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"
APPROVAL_TABLE_MISSING = "table_missing"


# ── Password utilities ─────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Hash a plain text password using bcrypt. Never store plain passwords."""
    if not plain_password or len(plain_password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed.encode("utf-8")
        )
    except Exception:
        return False


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_registration_inputs(
    username: str,
    email: str,
    password: str,
    confirm_password: str,
    role: str,
) -> list[str]:
    """
    Validate registration form inputs.
    Returns list of error strings. Empty list = all valid.
    """
    errors: list[str] = []

    # Username
    if not username or len(username.strip()) < 3:
        errors.append("❌ Username must be at least 3 characters.")
    if not username.replace("_", "").replace("-", "").isalnum():
        errors.append("❌ Username can only contain letters, numbers, hyphens and underscores.")

    # Email
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        errors.append("❌ Please enter a valid email address.")

    # Password
    if not password or len(password) < 6:
        errors.append("❌ Password must be at least 6 characters.")
    if password != confirm_password:
        errors.append("❌ Passwords do not match.")

    # Role
    if role not in ("staff", "customer", "admin", "supplier"):
        errors.append("❌ Invalid role selected.")

    return errors


def validate_login_inputs(username: str, password: str) -> list[str]:
    """Validate login form inputs."""
    errors: list[str] = []
    if not username or len(username.strip()) < 1:
        errors.append("❌ Please enter your username.")
    if not password or len(password) < 1:
        errors.append("❌ Please enter your password.")
    return errors


def _resolve_customer_id(client, email: str) -> str | None:
    """Find the matching customer profile for an email address."""
    if not email:
        return None
    try:
        response = (
            client.table("customers")
            .select("customer_id")
            .ilike("email", email.strip().lower())
            .limit(1)
            .execute()
        )
    except Exception:
        return None

    if not response.data:
        return None
    return response.data[0].get("customer_id")


def _generate_customer_id(client) -> str:
    """Generate the next CUST-prefixed customer ID."""
    highest = 0
    try:
        rows = client.table("customers").select("customer_id").execute().data or []
    except Exception:
        rows = []

    for row in rows:
        raw_customer_id = str(row.get("customer_id") or "").strip()
        match = re.match(r"^CUST(\d+)$", raw_customer_id, flags=re.IGNORECASE)
        if match:
            highest = max(highest, int(match.group(1)))

    return f"CUST{highest + 1:04d}"


def _create_customer_profile(client, username: str, email: str) -> str | None:
    """Create a customer record for a newly registered customer account if needed."""
    existing_customer_id = _resolve_customer_id(client, email)
    if existing_customer_id:
        return existing_customer_id

    username_clean = (username or "").strip()
    email_clean = (email or "").strip().lower()
    customer_id = _generate_customer_id(client)

    payload_variants = [
        {
            "customer_id": customer_id,
            "first_name": username_clean,
            "email": email_clean,
            "is_active": True,
            "email_notification_enabled": True,
            "promotional_emails_allowed": True,
            "join_date": datetime.now().date().isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
        {
            "customer_id": customer_id,
            "first_name": username_clean,
            "email": email_clean,
        },
        {
            "customer_id": customer_id,
            "email": email_clean,
        },
    ]

    for payload in payload_variants:
        try:
            client.table("customers").insert(payload).execute()
            resolved = _resolve_customer_id(client, email_clean)
            if resolved:
                return resolved
        except Exception:
            continue

    return customer_id


# ── Database operations ────────────────────────────────────────────────────────

def register_user(
    username: str,
    email: str,
    password: str,
    role: str = "staff",
    supplier_id: str | None = None,
) -> tuple[bool, str]:
    """
    Register a new user.
    Returns (success: bool, message: str).
    """
    try:
        client = get_client()

        # Check if username already exists
        existing = (
            client.table("users")
            .select("user_id")
            .eq("username", username.strip().lower())
            .execute()
        )
        if existing.data:
            return False, "❌ Username already taken. Please choose another."

        # Check if email already exists
        existing_email = (
            client.table("users")
            .select("user_id")
            .eq("email", email.strip().lower())
            .execute()
        )
        if existing_email.data:
            return False, "❌ Email already registered. Please login instead."

        if role == "supplier" and not (supplier_id or "").strip():
            return False, "❌ Supplier accounts require a Supplier ID."

        # Hash password and insert (user_id is auto-increment integer)
        hashed = hash_password(password)
        payload = {
            "username": username.strip().lower(),
            "email": email.strip().lower(),
            "password_hash": hashed,
            "role": role,
            "created_at": datetime.now().isoformat(),
        }

        # Some deployments may not have users.supplier_id yet.
        if role == "supplier":
            payload["supplier_id"] = (supplier_id or None)

        try:
            client.table("users").insert(payload).execute()
        except Exception as insert_exc:
            err = str(insert_exc).lower()
            if role == "supplier" and "supplier_id" in err and "column" in err:
                # Fallback for older schemas: create account without supplier_id and
                # link during login using suppliers.email when possible.
                payload.pop("supplier_id", None)
                client.table("users").insert(payload).execute()
                return True, (
                    "✅ Account created successfully. "
                    "Note: users.supplier_id is missing in DB; supplier linking will use email."
                )
            raise

        if role == "customer":
            try:
                created_user = (
                    client.table("users")
                    .select("user_id")
                    .eq("username", username.strip().lower())
                    .limit(1)
                    .execute()
                )
                user_id = created_user.data[0].get("user_id") if created_user.data else None
                customer_id = _create_customer_profile(client, username, email)
                if customer_id and user_id is not None:
                    try:
                        client.table("users").update({"customer_id": customer_id}).eq("user_id", user_id).execute()
                    except Exception:
                        pass
            except Exception:
                pass

        # Staff accounts must be approved by admin before first login.
        if role == "staff":
            created_user = (
                client.table("users")
                .select("user_id")
                .eq("username", username.strip().lower())
                .limit(1)
                .execute()
            )
            if not created_user.data:
                return False, "❌ Registration failed: unable to locate newly created account."

            user_id = created_user.data[0].get("user_id")
            if user_id is None:
                return False, "❌ Registration failed: missing user_id for approval workflow."

            try:
                client.table("staff_approvals").upsert(
                    {
                        "user_id": user_id,
                        "approval_status": APPROVAL_PENDING,
                        "requested_at": datetime.now().isoformat(),
                        "reviewed_at": None,
                        "reviewed_by": None,
                    },
                    on_conflict="user_id",
                ).execute()
            except Exception as approval_exc:
                return False, (
                    "❌ Staff account created, but approval workflow is not configured. "
                    f"Please run setup_staff_approvals.sql. Details: {approval_exc}"
                )

            return True, (
                "✅ Staff account created and submitted for admin approval. "
                "You can login after an admin approves your account."
            )

        return True, f"✅ Account created successfully! Welcome, {username}."

    except Exception as exc:
        return False, f"❌ Registration failed: {exc}"


def login_user(username: str, password: str) -> tuple[bool, str, dict | None]:
    """
    Authenticate a user.
    Returns (success: bool, message: str, user_dict | None).
    """
    try:
        client = get_client()
        # Try with supplier_id first; fallback keeps compatibility with older schema.
        try:
            response = (
                client.table("users")
                .select("user_id, username, email, role, password_hash, customer_id, supplier_id")
                .eq("username", username.strip().lower())
                .execute()
            )
        except Exception:
            response = (
                client.table("users")
                .select("user_id, username, email, role, password_hash, customer_id")
                .eq("username", username.strip().lower())
                .execute()
            )

        if not response.data:
            return False, "❌ Username not found.", None

        user = response.data[0]

        if not verify_password(password, user["password_hash"]):
            return False, "❌ Incorrect password.", None

        # Gate staff users until approved by an admin.
        if user.get("role") == "staff":
            approval_status = _get_staff_approval_status(client, user.get("user_id"))
            if approval_status is None:
                # Legacy staff accounts may not have an approval row yet.
                try:
                    client.table("staff_approvals").upsert(
                        {
                            "user_id": user.get("user_id"),
                            "approval_status": APPROVAL_PENDING,
                            "requested_at": datetime.now().isoformat(),
                            "reviewed_at": None,
                            "reviewed_by": None,
                        },
                        on_conflict="user_id",
                    ).execute()
                    approval_status = APPROVAL_PENDING
                except Exception:
                    approval_status = APPROVAL_TABLE_MISSING

            if approval_status == APPROVAL_PENDING:
                return False, "⏳ Your staff account is pending admin approval.", None
            if approval_status == APPROVAL_REJECTED:
                return False, "❌ Your staff account was rejected. Contact admin.", None
            if approval_status == APPROVAL_TABLE_MISSING:
                return False, "❌ Staff approval system not configured. Ask admin to run setup_staff_approvals.sql.", None

        # Backward-compatible supplier linking: if users.supplier_id is unavailable,
        # try mapping by suppliers.email so supplier dashboard can still open.
        if user.get("role") == "supplier" and not user.get("supplier_id"):
            user_email = (user.get("email") or "").strip().lower()
            if user_email:
                try:
                    supplier_match = (
                        client.table("suppliers")
                        .select("supplier_id")
                        .ilike("email", user_email)
                        .limit(1)
                        .execute()
                    )
                    if supplier_match.data:
                        user["supplier_id"] = supplier_match.data[0].get("supplier_id")
                except Exception:
                    pass

        if user.get("role") == "customer" and not user.get("customer_id"):
            try:
                customer_id = _resolve_customer_id(client, user.get("email", ""))
                if customer_id:
                    user["customer_id"] = customer_id
                    try:
                        client.table("users").update({"customer_id": customer_id}).eq("user_id", user.get("user_id")).execute()
                    except Exception:
                        pass
            except Exception:
                pass

        # Remove hash before storing in session
        user_safe = {k: v for k, v in user.items() if k != "password_hash"}
        return True, f"✅ Welcome back, {user['username']}!", user_safe

    except Exception as exc:
        return False, f"❌ Login failed: {exc}", None


# ── Session management ─────────────────────────────────────────────────────────

def init_session() -> None:
    """Initialize session state keys if not already set."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "current_page" not in st.session_state:
        st.session_state.current_page = "login"


def get_current_user() -> dict | None:
    """Return current logged-in user dict or None."""
    return st.session_state.get("user", None)


def is_authenticated() -> bool:
    """Check if user is logged in."""
    return st.session_state.get("authenticated", False)


def get_user_role() -> str:
    """Return role of current user: 'staff', 'customer', 'admin', or 'supplier'."""
    user = get_current_user()
    return user.get("role", "") if user else ""


def logout() -> None:
    """Clear session and redirect to login."""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.current_page = "login"
    st.rerun()


def require_auth(allowed_roles: list[str] | None = None) -> None:
    """
    Call at top of any protected page.
    Redirects to login if not authenticated.
    Redirects to main dashboard if wrong role.
    """
    init_session()
    if not is_authenticated():
        st.session_state.current_page = "login"
        st.rerun()
    if allowed_roles and get_user_role() not in allowed_roles:
        st.error(f"⛔ Access denied. This page requires role: {', '.join(allowed_roles)}")
        st.stop()


def _get_staff_approval_status(client, user_id) -> str | None:
    """Return staff approval status for user_id, None when table/row is missing."""
    if not user_id:
        return None
    try:
        response = (
            client.table("staff_approvals")
            .select("approval_status")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return APPROVAL_TABLE_MISSING

    if not response.data:
        return None
    return response.data[0].get("approval_status")


def fetch_pending_staff_approvals() -> list[dict]:
    """Return pending staff approval requests with user details."""
    client = get_client()
    approvals = (
        client.table("staff_approvals")
        .select("user_id,approval_status,requested_at")
        .eq("approval_status", APPROVAL_PENDING)
        .order("requested_at", desc=False)
        .execute()
    )

    pending_rows = approvals.data or []
    if not pending_rows:
        return []

    user_ids = [row.get("user_id") for row in pending_rows if row.get("user_id") is not None]
    users = (
        client.table("users")
        .select("user_id,username,email,role,created_at")
        .in_("user_id", user_ids)
        .execute()
    )
    user_map = {u.get("user_id"): u for u in (users.data or [])}

    merged = []
    for row in pending_rows:
        uid = row.get("user_id")
        u = user_map.get(uid, {})
        merged.append(
            {
                "user_id": uid,
                "username": u.get("username", "unknown"),
                "email": u.get("email", ""),
                "role": u.get("role", ""),
                "created_at": u.get("created_at"),
                "requested_at": row.get("requested_at"),
            }
        )
    return merged


def fetch_staff_approval_history(limit: int = 200) -> list[dict]:
    """Return approved/rejected staff approval history with user details."""
    client = get_client()
    approvals = (
        client.table("staff_approvals")
        .select("user_id,approval_status,requested_at,reviewed_at,reviewed_by")
        .in_("approval_status", [APPROVAL_APPROVED, APPROVAL_REJECTED])
        .order("reviewed_at", desc=True)
        .limit(int(limit))
        .execute()
    )

    history_rows = approvals.data or []
    if not history_rows:
        return []

    user_ids = [row.get("user_id") for row in history_rows if row.get("user_id") is not None]
    users = (
        client.table("users")
        .select("user_id,username,email,role,created_at")
        .in_("user_id", user_ids)
        .execute()
    )
    user_map = {u.get("user_id"): u for u in (users.data or [])}

    merged = []
    for row in history_rows:
        uid = row.get("user_id")
        u = user_map.get(uid, {})
        merged.append(
            {
                "user_id": uid,
                "username": u.get("username", "unknown"),
                "email": u.get("email", ""),
                "role": u.get("role", ""),
                "created_at": u.get("created_at"),
                "approval_status": row.get("approval_status", ""),
                "requested_at": row.get("requested_at"),
                "reviewed_at": row.get("reviewed_at"),
                "reviewed_by": row.get("reviewed_by", ""),
            }
        )
    return merged


def review_staff_approval(user_id: int, approve: bool, reviewed_by: str) -> tuple[bool, str]:
    """Approve or reject a pending staff account."""
    client = get_client()
    status = APPROVAL_APPROVED if approve else APPROVAL_REJECTED
    try:
        client.table("staff_approvals").upsert(
            {
                "user_id": user_id,
                "approval_status": status,
                "reviewed_at": datetime.now().isoformat(),
                "reviewed_by": reviewed_by,
            },
            on_conflict="user_id",
        ).execute()
        action = "approved" if approve else "rejected"
        return True, f"✅ Staff account {action}."
    except Exception as exc:
        return False, f"❌ Failed to update approval status: {exc}"