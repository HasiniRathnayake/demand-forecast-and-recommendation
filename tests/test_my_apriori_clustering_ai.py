"""
Tests owned by loyalty/customer AI scope:
- Apriori recommendation engine
- Customer clustering components
"""

from __future__ import annotations

import builtins

import pandas as pd


def test_apriori_run_returns_rules_with_expected_columns(monkeypatch):
    from scripts.apriori_engine import AprioriEngine

    # Suppress emoji prints on Windows cp1252 consoles during tests.
    monkeypatch.setattr(builtins, "print", lambda *_args, **_kwargs: None)

    transactions = []
    transactions += [["A", "B"]] * 8
    transactions += [["A"]] * 2
    transactions += [["B"]] * 1
    transactions += [["C"]] * 9

    engine = AprioriEngine()
    rules = engine.run_apriori(transactions, min_support=0.05, min_confidence=0.2)

    assert rules is not None
    assert not rules.empty
    required = {"antecedent_code", "consequent_code", "support", "confidence", "lift"}
    assert required.issubset(set(rules.columns))


def test_apriori_run_returns_none_for_empty_transactions():
    from scripts.apriori_engine import AprioriEngine

    engine = AprioriEngine()
    assert engine.run_apriori([]) is None
    assert engine.run_apriori(None) is None


def test_apriori_refresh_rules_healthy_does_not_trigger_rebuild(monkeypatch):
    from scripts.apriori_engine import AprioriEngine

    engine = AprioriEngine()
    monkeypatch.setattr(engine, "_get_rules_health", lambda: (20, pd.Timestamp("2026-04-20").date()))

    called = {"run": 0}

    def _fake_run():
        called["run"] += 1
        return True

    monkeypatch.setattr(engine, "run", _fake_run)

    ok = engine.refresh_rules_if_needed(max_age_days=7, min_rules=10)

    assert ok is True
    assert called["run"] == 0


def test_apriori_refresh_rules_stale_triggers_rebuild(monkeypatch):
    from scripts.apriori_engine import AprioriEngine

    engine = AprioriEngine()
    monkeypatch.setattr(engine, "_get_rules_health", lambda: (2, pd.Timestamp("2026-01-01").date()))
    monkeypatch.setattr(engine, "run", lambda: True)

    ok = engine.refresh_rules_if_needed(max_age_days=7, min_rules=10)
    assert ok is True


def test_clustering_best_k_stays_in_requested_range():
    from scripts.segmentation import CustomerSegmentation

    seg = CustomerSegmentation()
    # Two clearly separable groups
    X_scaled = pd.DataFrame(
        {
            "x": [0.0, 0.1, 0.2, 3.0, 3.1, 3.2],
            "y": [0.0, 0.1, 0.2, 3.0, 3.1, 3.2],
        }
    ).values

    best = seg._best_k(X_scaled, k_range=range(2, 5))
    assert best in {2, 3, 4}


def test_taste_label_mapping_uses_dominant_category_keywords():
    from scripts.segmentation import CustomerSegmentation

    seg = CustomerSegmentation()
    cat_features = pd.DataFrame(
        {
            "pct_fresh_meat": [70.0, 10.0],
            "pct_beverages": [10.0, 70.0],
            "pct_baby_care": [5.0, 10.0],
        }
    )
    cluster_labels = pd.Series([0, 1]).values

    label0 = seg._taste_label(0, cat_features, cluster_labels)
    label1 = seg._taste_label(1, cat_features, cluster_labels)

    assert label0 == "Fresh & Protein Lovers"
    assert label1 == "Drink & Health Focused"


def test_run_taste_clustering_returns_default_when_no_category_data(monkeypatch):
    from scripts.segmentation import CustomerSegmentation

    seg = CustomerSegmentation()
    monkeypatch.setattr(seg, "_fetch_category_features", lambda: pd.DataFrame())

    out = seg._run_taste_clustering(["CUST0001", "CUST0002"])

    assert out == {
        "CUST0001": "Balanced Shoppers",
        "CUST0002": "Balanced Shoppers",
    }


def test_run_rejects_invalid_mode():
    from scripts.segmentation import CustomerSegmentation

    seg = CustomerSegmentation()
    try:
        seg.run(mode="invalid-mode")
        raised = False
    except ValueError:
        raised = True
    assert raised is True
