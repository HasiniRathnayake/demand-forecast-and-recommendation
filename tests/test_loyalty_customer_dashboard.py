"""
Unit tests for customer dashboard and loyalty management helper logic.
These tests avoid Streamlit rendering and live database access.
"""

from datetime import date, datetime


class _FixedTodayDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 4, 20)


def test_format_promotion_subject_strips_brand_labels():
    from pages import customer_dashboard as dashboard

    assert dashboard._format_promotion_subject("🎉 Sunrise Super — Weekend Saver — Sunrise Super") == "Weekend Saver"
    assert dashboard._format_promotion_subject("   ") == "Special Promotion"


def test_extract_promotion_window_with_explicit_range():
    from pages import customer_dashboard as dashboard

    start, end = dashboard._extract_promotion_window(
        "Offer valid from 01 Apr 2026 to 10 Apr 2026.",
        datetime(2026, 4, 1),
    )

    assert start == date(2026, 4, 1)
    assert end == date(2026, 4, 10)


def test_extract_promotion_window_with_valid_until():
    from pages import customer_dashboard as dashboard

    start, end = dashboard._extract_promotion_window(
        "This promotion is valid until 30 Apr 2026.",
        datetime(2026, 4, 12),
    )

    assert start == date(2026, 4, 12)
    assert end == date(2026, 4, 30)


def test_get_active_promotions_filters_expired_and_formats(monkeypatch):
    from pages import customer_dashboard as dashboard

    monkeypatch.setattr(dashboard, "date", _FixedTodayDate)

    rows = [
        ("🎉 Sunrise Super — Weekend Saver", datetime(2026, 4, 18), "Offer valid from 18 Apr 2026 to 25 Apr 2026."),
        ("Sunrise Super — Expired Deal", datetime(2026, 4, 1), "Offer valid until 05 Apr 2026."),
    ]

    promotions = dashboard._get_active_promotions(rows)

    assert len(promotions) == 1
    assert promotions[0]["subject"] == "Weekend Saver"
    assert promotions[0]["start_date"] == date(2026, 4, 18)
    assert promotions[0]["end_date"] == date(2026, 4, 25)


def test_assignment_segment_column_prefers_segment_id(monkeypatch):
    from pages import loyalty_home

    class FakeDB:
        def fetch_all(self, *_args, **_kwargs):
            return [("segment_id",), ("product_preference",)]

    monkeypatch.setattr(loyalty_home, "DatabaseConnection", lambda: FakeDB())

    assert loyalty_home._assignment_segment_column() == "segment_id"


def test_assignment_taste_column_prefers_product_preference(monkeypatch):
    from pages import loyalty_home

    class FakeDB:
        def fetch_all(self, *_args, **_kwargs):
            return [("segment_id",), ("product_preference",)]

    monkeypatch.setattr(loyalty_home, "DatabaseConnection", lambda: FakeDB())

    assert loyalty_home._assignment_taste_column() == "product_preference"


def test_normalize_taste_label_maps_known_labels():
    from pages import loyalty_home

    assert loyalty_home._normalize_taste_label("Balanced Shoppers") == "🥦 balanced shoppers"
    assert loyalty_home._normalize_taste_label("Fresh & Protein Lovers") == "🐟 fresh & protein lovers"
    assert loyalty_home._normalize_taste_label("Unknown Segment") == "Unknown Segment"


def test_cluster_by_taste_preferences_alias_calls_run_with_taste(monkeypatch):
    from scripts.segmentation import CustomerSegmentation

    called = {}

    def fake_run(self, mode=None):
        called["mode"] = mode
        return [{"customer_id": 1}]

    monkeypatch.setattr(CustomerSegmentation, "run", fake_run)

    seg = CustomerSegmentation()
    result = seg.cluster_by_taste_preferences()

    assert called["mode"] == "taste"
    assert result == [{"customer_id": 1}]


def test_segmentation_run_rejects_unknown_mode():
    from scripts.segmentation import CustomerSegmentation

    seg = CustomerSegmentation()

    try:
        seg.run(mode="invalid")
        raised = False
    except ValueError as exc:
        raised = True
        assert "mode must be one of" in str(exc)

    assert raised is True