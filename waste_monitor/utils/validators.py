"""
utils/validators.py
───────────────────
All input validation logic for the Waste & Performance Monitor.
Each function returns (is_valid: bool, message: str).

Author : IT24103258
Module : Waste & Performance Monitor
"""

from __future__ import annotations

import re
from datetime import date

# ─── Constants ───────────────────────────────────────────────────────────────

PRODUCT_CODE_PATTERN = re.compile(r"^[A-Za-z]{1,6}\d{1,6}$")
MAX_PRICE_PER_KG     = 100_000   # Rs.
MAX_QUANTITY_KG      = 10_000    # kg

VALID_WASTE_REASONS  = [
    "Expired",
    "Damaged",
    "Spoiled",
    "Overstock",
    "Quality Issues",
    "Other",
]

# ─── Validators ──────────────────────────────────────────────────────────────

def validate_product_code_format(code: str) -> tuple[bool, str]:
    """
    Check that the product code is non-empty and matches the required format
    (1–6 letters followed by 1–6 digits, e.g. RICE001, OIL003).
    Returns the normalised (uppercased) code in the message on success.
    """
    code = code.strip()
    if not code:
        return False, "Product code is required."
    if not PRODUCT_CODE_PATTERN.match(code):
        return (
            False,
            "Invalid product code format. "
            "Use 1–6 letters followed by 1–6 digits (e.g. RICE001, OIL003).",
        )
    return True, code.upper()


def validate_waste_reason(reason: str) -> tuple[bool, str]:
    """Ensure a valid reason has been selected from the predefined list."""
    if not reason or reason not in VALID_WASTE_REASONS:
        return (
            False,
            f"Please select a valid waste reason: "
            f"{', '.join(VALID_WASTE_REASONS)}.",
        )
    return True, ""


def validate_waste_date(waste_date: date) -> tuple[bool, str]:
    """Waste date must not be in the future."""
    if not isinstance(waste_date, date):
        return False, "Invalid date."
    if waste_date > date.today():
        return False, "Waste date cannot be a future date."
    return True, ""


def validate_price_per_kg(price: float) -> tuple[bool, str]:
    """Price per kg must be a positive number within a realistic range."""
    try:
        price = float(price)
    except (TypeError, ValueError):
        return False, "Price per kg must be a valid number."
    if price <= 0:
        return False, "Price per kg must be greater than 0."
    if price > MAX_PRICE_PER_KG:
        return (
            False,
            f"Price per kg seems unrealistically high. "
            f"Maximum allowed is Rs. {MAX_PRICE_PER_KG:,}.",
        )
    return True, ""


def validate_quantity(qty: float) -> tuple[bool, str]:
    """Quantity must be a positive decimal within a realistic range."""
    try:
        qty = float(qty)
    except (TypeError, ValueError):
        return False, "Quantity must be a valid number."
    if qty <= 0:
        return False, "Quantity must be greater than 0."
    if qty > MAX_QUANTITY_KG:
        return (
            False,
            f"Quantity seems unrealistically high. "
            f"Maximum allowed is {MAX_QUANTITY_KG:,} kg.",
        )
    return True, ""


def validate_actual_sales(value: float) -> tuple[bool, str]:
    """Actual sales value must be zero or positive."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False, "Actual sales must be a valid number."
    if value < 0:
        return False, "Actual sales cannot be negative."
    return True, ""


def validate_waste_record_form(
    product_code: str,
    waste_date: date,
    quantity: float,
    waste_reason: str,
    price_per_kg: float,
) -> list[str]:
    """
    Run all validations for the waste record form.
    Returns a list of error messages (empty list = all valid).
    NOTE: DB existence check is done separately in the service layer.
    """
    errors: list[str] = []

    ok, msg = validate_product_code_format(product_code)
    if not ok:
        errors.append(msg)

    ok, msg = validate_waste_date(waste_date)
    if not ok:
        errors.append(msg)

    ok, msg = validate_quantity(quantity)
    if not ok:
        errors.append(msg)

    ok, msg = validate_waste_reason(waste_reason)
    if not ok:
        errors.append(msg)

    ok, msg = validate_price_per_kg(price_per_kg)
    if not ok:
        errors.append(msg)

    return errors
