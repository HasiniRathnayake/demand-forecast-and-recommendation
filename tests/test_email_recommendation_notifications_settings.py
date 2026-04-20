"""
Focused unit tests for loyalty emails, product recommendations,
customer notifications, settings persistence, clustering, and validations.
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd


class FakeDB:
    def __init__(self, fetch_one_result=None, fetch_all_result=None):
        self.fetch_one_result = fetch_one_result
        self.fetch_all_result = fetch_all_result
        self.executed = []

    def fetch_one(self, *_args, **_kwargs):
        return self.fetch_one_result

    def fetch_all(self, *_args, **_kwargs):
        return self.fetch_all_result

    def execute_query(self, query, params=None):
        self.executed.append((query, params))
        return True


def test_build_email_html_formats_offer_and_escapes_content():
    from scripts.email_sender import EmailSender

    sender = EmailSender()
    offer = {
        "customer_name": "Nimal",
        "offer_text": "20% OFF just for you!",
        "discount_pct": 20,
        "segment": "VIP Customer",
        "taste_preference": "<script>alert(1)</script>",
        "campaign_message": "Hello Nimal\nEnjoy this offer",
        "promo_start": "2026-04-20",
        "promo_end": "2026-04-27",
        "recommended": [
            {
                "product_name": "Basmati Rice",
                "category": "Rice",
                "unit_price": 200.0,
                "offer_price": 160.0,
                "reason": "Frequently bought together",
            }
        ],
    }

    html = sender.build_email_html(offer)

    assert "Hi Nimal" in html
    assert "20% OFF just for you!" in html
    assert "Hello Nimal<br>Enjoy this offer" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Save Rs.40.00" in html
    assert "valid from 2026-04-20 to 2026-04-27" in html


def test_send_promotional_emails_uses_test_address_and_logs(monkeypatch):
    from scripts.email_sender import EmailSender

    sender = EmailSender()
    sender.email_user = "tester@example.com"
    sender.email_from = "store@example.com"
    sender.email_pass = "secret"
    sender.smtp_host = "smtp.example.com"
    sender.smtp_port = 587

    smtp_server = MagicMock()
    smtp_server.__enter__.return_value = smtp_server
    smtp_server.__exit__.return_value = None
    monkeypatch.setattr("scripts.email_sender.smtplib.SMTP", lambda *_args, **_kwargs: smtp_server)

    log_calls = []
    monkeypatch.setattr(
        sender,
        "log_email",
        lambda *args, **kwargs: log_calls.append((args, kwargs)),
    )

    offers = [
        {
            "customer_id": 1,
            "customer_name": "Nimal",
            "email": "nimal@example.com",
            "segment": "VIP Customer",
            "offer_text": "20% OFF just for you!",
            "discount_pct": 20,
            "recommended": [],
            "email_enabled": True,
            "promo_allowed": True,
        },
        {
            "customer_id": 2,
            "customer_name": "Kamal",
            "email": "kamal@example.com",
            "segment": "Regular Customer",
            "offer_text": "10% OFF this week!",
            "discount_pct": 10,
            "recommended": [],
            "email_enabled": False,
            "promo_allowed": True,
        },
    ]

    result = sender.send_promotional_emails(offers, test_mode=True)

    assert result["sent"] == 1
    assert result["skipped"] == 1
    assert result["failed"] == 0
    smtp_server.sendmail.assert_called_once()
    sent_to = smtp_server.sendmail.call_args.args[1]
    assert sent_to == "tester@example.com"
    assert len(log_calls) == 1


def test_generate_offer_for_customer_combines_apriori_and_category_fallback(monkeypatch):
    from scripts.offers_engine import OffersEngine

    engine = OffersEngine()
    monkeypatch.setattr(
        engine.apriori,
        "get_recommendations",
        lambda *_args, **_kwargs: [
            {
                "product_code": "P1",
                "product_name": "Milk",
                "category": "Dairy",
                "unit_price": 100.0,
                "offer_price": 80.0,
                "reason": "Frequently bought together",
            }
        ],
    )
    monkeypatch.setattr(engine, "get_customer_favourite_categories", lambda *_args, **_kwargs: ["Dairy"])
    monkeypatch.setattr(
        engine.db,
        "fetch_all",
        lambda *_args, **_kwargs: [
            ("P2", "Cheese", "Dairy", 200.0, 170.0, 15),
            ("P3", "Yogurt", "Dairy", 50.0, 45.0, 10),
        ],
    )

    customer = {
        "customer_id": 7,
        "first_name": "Asha",
        "email": "asha@example.com",
        "segment": "Regular Customer",
        "email_enabled": True,
        "promo_allowed": True,
    }

    offer = engine.generate_offer_for_customer(customer)

    assert offer["discount_pct"] == 10
    assert offer["offer_text"] == "10% OFF this week!"
    assert len(offer["recommended"]) == 3
    assert len({row["product_code"] for row in offer["recommended"]}) == 3
    assert offer["recommended"][0]["reason"] == "Frequently bought together"
    assert offer["recommended"][1]["reason"] == "Your favorite category"


def test_apriori_recommendations_fall_back_to_popular_products_when_no_history(monkeypatch):
    from scripts.apriori_engine import AprioriEngine

    engine = AprioriEngine()

    def fake_fetch_all(query, params=None):
        if "FROM transaction_items ti" in query and "JOIN transactions" in query and "WHERE t.customer_id" in query:
            return []
        if "FROM product_catalog p" in query:
            return [
                ("P10", "Sugar", "Sugar", 150.0, 120.0, 40),
                ("P11", "Flour", "Flour", 180.0, 160.0, 30),
            ]
        return []

    monkeypatch.setattr(engine.db, "fetch_all", fake_fetch_all)

    recommendations = engine.get_recommendations(99, top_n=2)

    assert len(recommendations) == 2
    assert all(item["reason"] == "Popular product" for item in recommendations)


def test_apriori_recommendations_use_rules_before_popular_fallback(monkeypatch):
    from scripts.apriori_engine import AprioriEngine

    engine = AprioriEngine()

    def fake_fetch_all(query, params=None):
        if "WHERE t.customer_id" in query:
            return [("P1",), ("P2",)]
        if "FROM association_rules ar" in query:
            return [
                ("P3", "Yogurt", "Dairy", 100.0, 85.0, 0.92, 1.6),
            ]
        if "FROM product_catalog p" in query:
            return [
                ("P4", "Rice", "Rice", 200.0, 190.0, 50),
                ("P5", "Tea", "Beverages", 120.0, 110.0, 45),
            ]
        return []

    monkeypatch.setattr(engine.db, "fetch_all", fake_fetch_all)

    recommendations = engine.get_recommendations(42, top_n=3)

    assert len(recommendations) == 3
    assert recommendations[0]["source"] == "association"
    assert recommendations[0]["product_code"] == "P3"
    assert recommendations[1]["reason"] == "Popular product"


def test_loyalty_clustering_marks_new_customers_and_returns_labels():
    from scripts.segmentation import CustomerSegmentation

    seg = CustomerSegmentation()
    df = pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4, 5],
            "first_name": ["A", "B", "C", "D", "E"],
            "email": ["a@example.com", "b@example.com", "c@example.com", "d@example.com", "e@example.com"],
            "email_enabled": [True, True, True, True, True],
            "promo_allowed": [True, True, True, True, True],
            "tx_count": [10, 8, 5, 3, 0],
            "total_spent": [10000, 8000, 5000, 2000, 0],
            "avg_basket": [1000, 1000, 1000, 700, 0],
            "days_since_last": [2, 5, 15, 40, 999],
            "segment_id": [None, None, None, None, None],
            "product_preference": [None, None, None, None, None],
        }
    )

    result = seg._run_loyalty_clustering(df)

    assert "loyalty_status" in result.columns
    assert len(result) == 5
    assert result.loc[result["customer_id"] == 5, "loyalty_status"].iloc[0] == "New Customer"
    assert result["loyalty_status"].notna().all()


def test_new_promo_count_counts_only_recent_promotions(monkeypatch):
    from pages import customer_dashboard as dashboard

    dashboard._get_new_promo_count.clear()
    monkeypatch.setattr(
        dashboard,
        "DatabaseConnection",
        lambda: FakeDB(fetch_one_result=(4,)),
    )

    count = dashboard._get_new_promo_count(12, date(2026, 4, 10))
    assert count == 4


def test_customer_settings_load_and_save_preferences(monkeypatch):
    from pages import customer_settings

    fake_db = FakeDB(fetch_one_result=("Asha", True, False))
    monkeypatch.setattr(customer_settings, "DatabaseConnection", lambda: fake_db)

    loaded = customer_settings._load_customer_preferences(77)
    assert loaded == ("Asha", True, False)

    saved = customer_settings._save_customer_preferences(77, False, False)
    assert saved is True
    assert fake_db.executed
    assert "UPDATE customers" in fake_db.executed[0][0]


def test_validation_helpers_cover_common_success_and_failure_paths():
    from utils.validators import (
        MAX_PRICE_PER_KG,
        MAX_QUANTITY_KG,
        validate_actual_sales,
        validate_price_per_kg,
        validate_product_code_format,
        validate_quantity,
        validate_waste_date,
        validate_waste_reason,
        validate_waste_record_form,
    )

    ok, msg = validate_product_code_format("rice001")
    assert ok is True
    assert msg == "RICE001"

    ok, msg = validate_product_code_format("")
    assert ok is False
    assert "required" in msg.lower()

    assert validate_waste_reason("Expired")[0] is True
    assert validate_waste_reason("Not valid")[0] is False

    assert validate_waste_date(date.today())[0] is True
    assert validate_waste_date(date.today().replace(year=date.today().year + 1))[0] is False
    assert validate_waste_date("2026-04-20")[0] is False

    assert validate_price_per_kg(100.0)[0] is True
    assert validate_price_per_kg(-1)[0] is False
    assert validate_price_per_kg(MAX_PRICE_PER_KG + 1)[0] is False

    assert validate_quantity(5)[0] is True
    assert validate_quantity(0)[0] is False
    assert validate_quantity(MAX_QUANTITY_KG + 1)[0] is False

    assert validate_actual_sales(0)[0] is True
    assert validate_actual_sales(-1)[0] is False

    errors = validate_waste_record_form(
        "bad-code",
        date.today().replace(year=date.today().year + 1),
        0,
        "Invalid",
        -5,
    )
    assert len(errors) >= 4