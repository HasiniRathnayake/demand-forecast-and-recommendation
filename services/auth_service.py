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
import streamlit as st
from datetime import datetime
from data.db_client import get_client


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
        client.table("users").insert({
            "username":      username.strip().lower(),
            "email":         email.strip().lower(),
            "password_hash": hashed,
            "role":          role,
            "supplier_id":   (supplier_id or None),
            "created_at":    datetime.now().isoformat(),
        }).execute()

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