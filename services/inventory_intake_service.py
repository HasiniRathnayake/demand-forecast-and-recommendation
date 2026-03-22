"""
services/inventory_intake_service.py
===================================
Core anomaly logic for Smart Inventory Intake.
"""

from __future__ import annotations


class SmartIntakeSystem:
    def detect_anomaly(self, expected_qty: float, actual_qty: float) -> tuple[bool, str, str]:
        """
        Compare AI expected quantity with physical count.

        Returns
        -------
        (is_anomaly, message, severity)
        """
        expected = float(expected_qty or 0.0)
        actual = float(actual_qty or 0.0)

        # No AI forecast available yet: allow logging without anomaly.
        if expected <= 0:
            return False, "No AI forecast found. Logging manual physical count.", "low"

        if expected == actual:
            return False, "Perfect match. Count aligns with AI forecast.", "none"

        variance_pct = abs(expected - actual) / expected

        if actual < (expected * 0.5):
            return (
                True,
                f"Massive shortage. AI predicted {expected:.2f}, but only {actual:.2f} counted.",
                "high",
            )
        if variance_pct <= 0.10:
            return False, f"Minor acceptable variance. Off by {abs(expected - actual):.2f} units.", "low"

        return True, f"Significant variance of {variance_pct * 100:.1f}%. Manager review required.", "medium"


def requires_remarks(is_anomaly: bool, remarks: str, min_len: int = 5) -> bool:
    """Return True when anomaly remarks are missing or too short."""
    if not is_anomaly:
        return False
    return len((remarks or "").strip()) < min_len
