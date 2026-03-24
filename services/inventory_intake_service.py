"""
services/inventory_intake_service.py
===================================
Core anomaly logic for Smart Inventory Intake.
"""

from __future__ import annotations


class SmartIntakeSystem:
    def detect_anomaly(self, expected_qty: float, actual_qty: float) -> tuple[bool, str, str]:
        """
        Compare ML system expected stock quantity with actual physical shelf count.

        Returns
        -------
        (is_anomaly, message, severity)
        """
        expected = float(expected_qty or 0.0)
        actual = float(actual_qty or 0.0)

        # No system tracking yet: allow logging without anomaly.
        if expected <= 0 and actual > 0:
            return False, "Initial stock log recorded. No prior system stock found.", "low"

        if expected == actual:
            return False, "Verified: Zero Shrinkage. Physical shelf count matches ML systemic stock perfectly.", "none"

        variance = expected - actual
        variance_pct = abs(variance) / max(expected, 1)

        # Severe Shrinkage/Theft (Missing Stock)
        if variance > 0 and variance_pct > 0.20:
            return (
                True,
                f"Severe Shrinkage! ML system tracked {expected:.0f} units, but only {actual:.0f} were found. ({variance:.0f} missing)",
                "high",
            )
            
        # Overstock (Found more than expected)
        if variance < 0 and variance_pct > 0.20:
             return (
                True,
                f"Severe Overage! ML system tracked {expected:.0f} units, but {actual:.0f} were found. Incorrect receiving assumed.",
                "medium",
            )
            
        # Minor discrepancy
        return False, f"Minor stock drift logged. Off by {abs(variance):.0f} units.", "low"


def requires_remarks(is_anomaly: bool, remarks: str, min_len: int = 5) -> bool:
    """Return True when anomaly remarks are missing or too short."""
    if not is_anomaly:
        return False
    return len((remarks or "").strip()) < min_len
