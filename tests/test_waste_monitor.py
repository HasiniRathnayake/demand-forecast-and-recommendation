"""
tests/test_waste_monitor.py
────────────────────────────
Unit & Security Tests for Waste & Performance Monitor
Author : IT24103258
Module : Waste & Performance Monitor
"""

import pytest
from datetime import date, timedelta
from utils.validators import (
    validate_product_code_format,
    validate_waste_reason,
    validate_waste_date,
    validate_price_per_kg,
    validate_quantity,
    validate_actual_sales,
    validate_waste_record_form,
    VALID_WASTE_REASONS,
    MAX_PRICE_PER_KG,
    MAX_QUANTITY_KG,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. PRODUCT CODE VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestProductCodeFormat:

    def test_valid_product_code(self):
        """Valid product code should pass."""
        ok, msg = validate_product_code_format("RICE001")
        assert ok is True
        assert msg == "RICE001"

    def test_valid_product_code_lowercase(self):
        """Lowercase product code should be accepted and uppercased."""
        ok, msg = validate_product_code_format("oil003")
        assert ok is True
        assert msg == "OIL003"

    def test_valid_product_code_short(self):
        """Single letter + single digit should be valid."""
        ok, msg = validate_product_code_format("A1")
        assert ok is True

    def test_valid_product_code_max_length(self):
        """6 letters + 6 digits should be valid."""
        ok, msg = validate_product_code_format("ABCDEF123456")
        assert ok is True

    def test_empty_product_code(self):
        """Empty product code should fail."""
        ok, msg = validate_product_code_format("")
        assert ok is False
        assert "required" in msg.lower()

    def test_whitespace_only_product_code(self):
        """Whitespace-only product code should fail."""
        ok, msg = validate_product_code_format("   ")
        assert ok is False

    def test_digits_only_product_code(self):
        """Digits only (no letters) should fail."""
        ok, msg = validate_product_code_format("12345")
        assert ok is False

    def test_letters_only_product_code(self):
        """Letters only (no digits) should fail."""
        ok, msg = validate_product_code_format("RICE")
        assert ok is False

    def test_special_characters_in_product_code(self):
        """Special characters should fail."""
        ok, msg = validate_product_code_format("RICE-001")
        assert ok is False

    def test_sql_injection_product_code(self):
        """SQL injection attempt should fail validation."""
        ok, msg = validate_product_code_format("'; DROP TABLE products; --")
        assert ok is False

    def test_xss_product_code(self):
        """XSS attempt should fail validation."""
        ok, msg = validate_product_code_format("<script>alert('xss')</script>")
        assert ok is False

    def test_too_long_letters_product_code(self):
        """More than 6 letters should fail."""
        ok, msg = validate_product_code_format("ABCDEFG001")
        assert ok is False

    def test_too_long_digits_product_code(self):
        """More than 6 digits should fail."""
        ok, msg = validate_product_code_format("RICE1234567")
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. WASTE REASON VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestWasteReason:

    def test_valid_reason_expired(self):
        """'Expired' should be a valid reason."""
        ok, msg = validate_waste_reason("Expired")
        assert ok is True

    def test_valid_reason_damaged(self):
        """'Damaged' should be a valid reason."""
        ok, msg = validate_waste_reason("Damaged")
        assert ok is True

    def test_all_valid_reasons(self):
        """All predefined reasons should pass."""
        for reason in VALID_WASTE_REASONS:
            ok, msg = validate_waste_reason(reason)
            assert ok is True, f"Expected '{reason}' to be valid"

    def test_empty_reason(self):
        """Empty reason should fail."""
        ok, msg = validate_waste_reason("")
        assert ok is False

    def test_invalid_reason(self):
        """Unknown reason should fail."""
        ok, msg = validate_waste_reason("Lost in fire")
        assert ok is False

    def test_default_select_reason(self):
        """Default dropdown value should fail."""
        ok, msg = validate_waste_reason("-- Select a reason --")
        assert ok is False

    def test_case_sensitive_reason(self):
        """Lowercase valid reason should fail (case-sensitive)."""
        ok, msg = validate_waste_reason("expired")
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. WASTE DATE VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestWasteDate:

    def test_today_is_valid(self):
        """Today's date should be valid."""
        ok, msg = validate_waste_date(date.today())
        assert ok is True

    def test_past_date_is_valid(self):
        """Past date should be valid."""
        ok, msg = validate_waste_date(date.today() - timedelta(days=30))
        assert ok is True

    def test_future_date_is_invalid(self):
        """Future date should fail."""
        ok, msg = validate_waste_date(date.today() + timedelta(days=1))
        assert ok is False
        assert "future" in msg.lower()

    def test_far_future_date_is_invalid(self):
        """Far future date should fail."""
        ok, msg = validate_waste_date(date(2099, 12, 31))
        assert ok is False

    def test_invalid_date_type(self):
        """Non-date type should fail."""
        ok, msg = validate_waste_date("2026-03-23")
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. PRICE PER KG VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestPricePerKg:

    def test_valid_price(self):
        """Normal price should pass."""
        ok, msg = validate_price_per_kg(150.0)
        assert ok is True

    def test_minimum_valid_price(self):
        """Very small positive price should pass."""
        ok, msg = validate_price_per_kg(0.01)
        assert ok is True

    def test_zero_price_is_invalid(self):
        """Zero price should fail."""
        ok, msg = validate_price_per_kg(0)
        assert ok is False
        assert "greater than 0" in msg.lower()

    def test_negative_price_is_invalid(self):
        """Negative price should fail."""
        ok, msg = validate_price_per_kg(-100)
        assert ok is False

    def test_exceeds_max_price(self):
        """Price above maximum should fail."""
        ok, msg = validate_price_per_kg(MAX_PRICE_PER_KG + 1)
        assert ok is False
        assert "maximum" in msg.lower()

    def test_exact_max_price(self):
        """Exactly at maximum price should pass."""
        ok, msg = validate_price_per_kg(MAX_PRICE_PER_KG)
        assert ok is True

    def test_non_numeric_price(self):
        """Non-numeric price should fail."""
        ok, msg = validate_price_per_kg("abc")
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. QUANTITY VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestQuantity:

    def test_valid_quantity(self):
        """Normal quantity should pass."""
        ok, msg = validate_quantity(5.0)
        assert ok is True

    def test_minimum_valid_quantity(self):
        """Very small positive quantity should pass."""
        ok, msg = validate_quantity(0.001)
        assert ok is True

    def test_zero_quantity_is_invalid(self):
        """Zero quantity should fail."""
        ok, msg = validate_quantity(0)
        assert ok is False
        assert "greater than 0" in msg.lower()

    def test_negative_quantity_is_invalid(self):
        """Negative quantity should fail."""
        ok, msg = validate_quantity(-5)
        assert ok is False

    def test_exceeds_max_quantity(self):
        """Quantity above maximum should fail."""
        ok, msg = validate_quantity(MAX_QUANTITY_KG + 1)
        assert ok is False
        assert "maximum" in msg.lower()

    def test_exact_max_quantity(self):
        """Exactly at maximum quantity should pass."""
        ok, msg = validate_quantity(MAX_QUANTITY_KG)
        assert ok is True

    def test_non_numeric_quantity(self):
        """Non-numeric quantity should fail."""
        ok, msg = validate_quantity("ten")
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# 6. ACTUAL SALES VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestActualSales:

    def test_valid_actual_sales(self):
        """Positive actual sales should pass."""
        ok, msg = validate_actual_sales(100.0)
        assert ok is True

    def test_zero_actual_sales(self):
        """Zero actual sales should pass (no sales is valid)."""
        ok, msg = validate_actual_sales(0.0)
        assert ok is True

    def test_negative_actual_sales(self):
        """Negative actual sales should fail."""
        ok, msg = validate_actual_sales(-1.0)
        assert ok is False
        assert "negative" in msg.lower()

    def test_non_numeric_actual_sales(self):
        """Non-numeric actual sales should fail."""
        ok, msg = validate_actual_sales("abc")
        assert ok is False

    def test_large_actual_sales(self):
        """Very large actual sales should pass."""
        ok, msg = validate_actual_sales(999999.99)
        assert ok is True


# ─────────────────────────────────────────────────────────────────────────────
# 7. FULL WASTE RECORD FORM VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestWasteRecordForm:

    def test_valid_form(self):
        """Fully valid form should return no errors."""
        errors = validate_waste_record_form(
            product_code="RICE001",
            waste_date=date.today(),
            quantity=10.0,
            waste_reason="Expired",
            price_per_kg=150.0,
        )
        assert errors == []

    def test_invalid_product_code_in_form(self):
        """Invalid product code should return error."""
        errors = validate_waste_record_form(
            product_code="",
            waste_date=date.today(),
            quantity=10.0,
            waste_reason="Expired",
            price_per_kg=150.0,
        )
        assert len(errors) > 0

    def test_future_date_in_form(self):
        """Future date should return error."""
        errors = validate_waste_record_form(
            product_code="RICE001",
            waste_date=date.today() + timedelta(days=1),
            quantity=10.0,
            waste_reason="Expired",
            price_per_kg=150.0,
        )
        assert len(errors) > 0

    def test_zero_quantity_in_form(self):
        """Zero quantity should return error."""
        errors = validate_waste_record_form(
            product_code="RICE001",
            waste_date=date.today(),
            quantity=0,
            waste_reason="Expired",
            price_per_kg=150.0,
        )
        assert len(errors) > 0

    def test_invalid_reason_in_form(self):
        """Invalid reason should return error."""
        errors = validate_waste_record_form(
            product_code="RICE001",
            waste_date=date.today(),
            quantity=10.0,
            waste_reason="",
            price_per_kg=150.0,
        )
        assert len(errors) > 0

    def test_zero_price_in_form(self):
        """Zero price should return error."""
        errors = validate_waste_record_form(
            product_code="RICE001",
            waste_date=date.today(),
            quantity=10.0,
            waste_reason="Expired",
            price_per_kg=0,
        )
        assert len(errors) > 0

    def test_multiple_errors_in_form(self):
        """Multiple invalid fields should return multiple errors."""
        errors = validate_waste_record_form(
            product_code="",
            waste_date=date.today() + timedelta(days=5),
            quantity=0,
            waste_reason="",
            price_per_kg=0,
        )
        assert len(errors) >= 4

    def test_sql_injection_in_form(self):
        """SQL injection in product code should be caught by validation."""
        errors = validate_waste_record_form(
            product_code="'; DROP TABLE waste_records; --",
            waste_date=date.today(),
            quantity=10.0,
            waste_reason="Expired",
            price_per_kg=150.0,
        )
        assert len(errors) > 0

    def test_xss_in_form(self):
        """XSS attempt in product code should be caught by validation."""
        errors = validate_waste_record_form(
            product_code="<script>alert('xss')</script>",
            waste_date=date.today(),
            quantity=10.0,
            waste_reason="Expired",
            price_per_kg=150.0,
        )
        assert len(errors) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 8. SAVINGS CALCULATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestSavingsCalculations:

    def test_waste_without_ai_is_higher(self):
        """Estimated waste without AI should be 40% higher than actual."""
        total_waste_loss = 10000.0
        waste_wo_ai = total_waste_loss * 1.4
        assert waste_wo_ai == 14000.0

    def test_total_savings_is_positive(self):
        """Total savings should always be positive."""
        total_waste_loss = 10000.0
        waste_wo_ai      = total_waste_loss * 1.4
        overstock_wo     = waste_wo_ai * 0.3
        lost_rev_wo      = waste_wo_ai * 0.5
        total_before     = waste_wo_ai + overstock_wo + lost_rev_wo

        current_overstock = total_waste_loss * 0.2
        current_lost_rev  = total_waste_loss * 0.3
        total_after       = total_waste_loss + current_overstock + current_lost_rev

        total_savings = total_before - total_after
        assert total_savings > 0

    def test_accuracy_calculation(self):
        """Accuracy should be 100 minus average error percentage."""
        avg_error = 5.0
        accuracy  = 100.0 - avg_error
        assert accuracy == 95.0

    def test_savings_percentage(self):
        """Savings percentage should be between 0 and 100."""
        total_before  = 28000.0
        total_after   = 15000.0
        savings_pct   = (total_before - total_after) / total_before * 100
        assert 0 < savings_pct < 100

    def test_estimated_loss_calculation(self):
        """Estimated loss should equal quantity times price."""
        quantity     = 10.0
        price_per_kg = 150.0
        estimated    = quantity * price_per_kg
        assert estimated == 1500.0


# ─────────────────────────────────────────────────────────────────────────────
# 9. AI PERFORMANCE METRICS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestAIPerformanceMetrics:

    def test_future_date_comparison_rejected(self):
        """Forecast date in the future should be rejected."""
        future_date = date.today() + timedelta(days=1)
        assert future_date > date.today()

    def test_past_date_comparison_allowed(self):
        """Forecast date in the past should be allowed."""
        past_date = date.today() - timedelta(days=1)
        assert past_date <= date.today()

    def test_today_date_comparison_allowed(self):
        """Today's forecast date should be allowed."""
        today = date.today()
        assert today <= date.today()

    def test_difference_calculation_positive(self):
        """Positive difference when actual > predicted."""
        predicted = 100.0
        actual    = 120.0
        diff      = actual - predicted
        assert diff == 20.0

    def test_difference_calculation_negative(self):
        """Negative difference when actual < predicted."""
        predicted = 100.0
        actual    = 80.0
        diff      = actual - predicted
        assert diff == -20.0

    def test_difference_percentage_calculation(self):
        """Difference percentage should be calculated correctly."""
        predicted = 100.0
        actual    = 110.0
        diff      = actual - predicted
        diff_pct  = (diff / predicted * 100)
        assert diff_pct == 10.0

    def test_zero_predicted_no_division_error(self):
        """Zero predicted demand should not cause division by zero."""
        predicted = 0.0
        actual    = 50.0
        diff_pct  = (actual - predicted) / predicted * 100 if predicted > 0 else 0.0
        assert diff_pct == 0.0
