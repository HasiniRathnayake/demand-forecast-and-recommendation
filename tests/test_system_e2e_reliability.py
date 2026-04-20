"""
System-level tests for loyalty management and customer dashboard workflow.

These tests use real database-backed components and are intentionally gated.
Run only when RUN_REALDB_SYSTEM_TESTS=1 is set in the environment.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest

from pages.customer_dashboard import (
    _get_active_promotions,
    _get_emails,
    _get_new_promo_count,
    _get_profile,
)
from pages.loyalty_home import _assignment_segment_column
from scripts.db_connection import DatabaseConnection
from scripts.email_sender import EmailSender
from scripts.offers_engine import OffersEngine
from scripts.segmentation import CustomerSegmentation


def _require_realdb_system_tests() -> None:
    if os.getenv("RUN_REALDB_SYSTEM_TESTS") != "1":
        pytest.skip("Set RUN_REALDB_SYSTEM_TESTS=1 to run real DB system tests.")


def _cleanup_test_email_subjects(db: DatabaseConnection, subject_prefix: str) -> None:
    db.execute_query("DELETE FROM email_log WHERE subject LIKE %s", [f"{subject_prefix}%"])


def _fetch_offer_ready_customers(limit: int = 5) -> list[dict]:
    db = DatabaseConnection()
    segment_col = _assignment_segment_column()
    rows = db.fetch_all(
        f"""
        SELECT
            c.customer_id,
            c.first_name,
            c.email,
            cs.segment_name,
            c.email_notification_enabled,
            c.promotional_emails_allowed,
            COALESCE(SUM(t.total_amount), 0) AS total_spent
        FROM customers c
        JOIN customer_segment_assignment csa ON c.customer_id = csa.customer_id
        JOIN customer_segments cs ON csa.{segment_col} = cs.segment_id
        LEFT JOIN transactions t ON c.customer_id = t.customer_id
        WHERE c.is_active = TRUE
        GROUP BY c.customer_id, c.first_name, c.email,
                 cs.segment_name, c.email_notification_enabled,
                 c.promotional_emails_allowed
        ORDER BY c.customer_id
        LIMIT %s
        """,
        [limit],
    )
    return [
        {
            "customer_id": r[0],
            "first_name": r[1],
            "email": r[2],
            "segment": r[3],
            "email_enabled": bool(r[4]),
            "promo_allowed": bool(r[5]),
            "total_spent": float(r[6] or 0.0),
            "tx_count": 1,
            "avg_basket": 0,
            "days_inactive": 0,
        }
        for r in rows
    ]


def test_system_e2e_loyalty_to_dashboard_email_flow_real_db():
    """
    Real end-to-end path:
    segmentation -> offer generation -> email_log write -> dashboard fetch path.
    """
    _require_realdb_system_tests()

    db = DatabaseConnection()
    subject_prefix = f"[E2E-SYSTEM-{uuid.uuid4().hex[:8]}]"

    try:
        # 1) Run segmentation pipeline against real DB assignments.
        seg_results = CustomerSegmentation().run(mode="rfm")
        assert isinstance(seg_results, list)
        assert len(seg_results) > 0

        # 2) Build offer-ready customer list from the real assignment tables.
        customers = _fetch_offer_ready_customers(limit=10)
        assert customers, "No segment-assigned active customers found."

        eligible = [c for c in customers if c["email_enabled"] and c["promo_allowed"] and c["email"]]
        if not eligible:
            pytest.skip("No email-eligible customers available for end-to-end system test.")

        # 3) Generate an offer with recommendation dependencies.
        offer = OffersEngine().generate_offer_for_customer(eligible[0])
        assert offer["recommended"] is not None

        # 4) Write a real sent promotional record through EmailSender logger.
        sender = EmailSender()
        offer["promo_start"] = "20 Apr 2026"
        offer["promo_end"] = "30 Apr 2026"
        offer["campaign_message"] = "System integration validation campaign"
        html_content = sender.build_email_html(offer)

        subject = f"{subject_prefix} \\U0001f389 {offer['offer_text']}"
        sender.log_email(
            customer_id=offer["customer_id"],
            email_type="promotional_system_test",
            subject=subject,
            html_content=html_content,
            status=True,
            segment=offer.get("segment"),
        )

        # 5) Validate dashboard fetch path sees the inserted record.
        _get_profile.clear()
        _get_emails.clear()
        _get_new_promo_count.clear()

        profile = _get_profile(offer["customer_id"])
        assert profile is not None

        emails = _get_emails(offer["customer_id"])
        assert any((row[0] or "").startswith(subject_prefix) for row in emails)

        active_promotions = _get_active_promotions(emails)
        assert isinstance(active_promotions, list)

        promo_count = _get_new_promo_count(offer["customer_id"], date.today() - timedelta(days=1))
        assert promo_count >= 1
    finally:
        _cleanup_test_email_subjects(db, subject_prefix)


def test_system_reliability_repeated_segmentation_runs_stable_real_db():
    """Repeated-run stability check for segmentation assignment output."""
    _require_realdb_system_tests()

    seg = CustomerSegmentation()
    run_ids = []
    run_counts = []

    for _ in range(3):
        results = seg.run(mode="taste")
        assert isinstance(results, list)
        assert len(results) > 0
        run_counts.append(len(results))
        run_ids.append({row["customer_id"] for row in results})

    # Customer identity set should be stable across close repeated runs.
    assert run_ids[0] == run_ids[1] == run_ids[2]
    # Counts should also remain stable.
    assert run_counts[0] == run_counts[1] == run_counts[2]


def test_system_reliability_dependency_failure_recovery_email_path_real_db(monkeypatch):
    """
    Dependency failure recovery scenario:
    SMTP failure should not crash flow and should log failed email status.
    """
    _require_realdb_system_tests()

    db = DatabaseConnection()
    subject_prefix = f"[E2E-FAILOVER-{uuid.uuid4().hex[:8]}]"

    customers = _fetch_offer_ready_customers(limit=5)
    eligible = [c for c in customers if c["email_enabled"] and c["promo_allowed"] and c["email"]]
    if not eligible:
        pytest.skip("No eligible customers available for SMTP failure recovery scenario.")

    sender = EmailSender()
    offer = OffersEngine().generate_offer_for_customer(eligible[0])
    offer["offer_text"] = f"{subject_prefix} failover campaign"

    try:
        class FailingSMTP:
            def __init__(self, *_args, **_kwargs):
                raise OSError("Simulated SMTP outage")

        monkeypatch.setattr("scripts.email_sender.smtplib.SMTP", FailingSMTP)

        summary = sender.send_promotional_emails([offer], test_mode=False)
        assert summary["sent"] == 0
        assert summary["failed"] == 1
        assert summary["results"][0]["status"] == "failed"

        row = db.fetch_one(
            """
            SELECT COUNT(*)
            FROM email_log
            WHERE customer_id = %s
              AND subject LIKE %s
              AND delivery_status = 'failed'
            """,
            [offer["customer_id"], f"%{subject_prefix}%"],
        )
        assert row and int(row[0]) >= 1
    finally:
        _cleanup_test_email_subjects(db, subject_prefix)


def test_system_reliability_notification_count_consistent_over_repeated_reads_real_db():
    """Long-run consistency check for dashboard notification counting path."""
    _require_realdb_system_tests()

    db = DatabaseConnection()
    subject_prefix = f"[E2E-CONSISTENCY-{uuid.uuid4().hex[:8]}]"

    customer = db.fetch_one(
        """
        SELECT customer_id
        FROM customers
        WHERE is_active = TRUE
          AND email_notification_enabled = TRUE
        ORDER BY customer_id
        LIMIT 1
        """
    )
    if not customer:
        pytest.skip("No active customer available for notification consistency scenario.")

    customer_id = int(customer[0])
    sender = EmailSender()

    try:
        sender.log_email(
            customer_id=customer_id,
            email_type="promotional_system_test",
            subject=f"{subject_prefix} consistency",
            html_content="Offer valid until 30 Apr 2026.",
            status=True,
            segment="Regular Customer",
        )

        _get_new_promo_count.clear()
        since = date.today() - timedelta(days=2)

        counts = [_get_new_promo_count(customer_id, since) for _ in range(3)]
        assert counts[0] == counts[1] == counts[2]
        assert counts[0] >= 1
    finally:
        _cleanup_test_email_subjects(db, subject_prefix)