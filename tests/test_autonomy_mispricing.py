"""Tests for the triangulated mispricing engine."""
from __future__ import annotations

from types import SimpleNamespace

from autonomy.mispricing import (
    MispricingAssessment,
    MispricingMonitor,
    assess_mispricing,
    _implied_yes_from_quotes,
)


def _mkt(ticker, yes_ask, no_ask):
    return SimpleNamespace(ticker=ticker, yes_ask=yes_ask, no_ask=no_ask)


def test_implied_yes_from_quotes_blends_both_sides():
    yes_cost, no_cost, mid = _implied_yes_from_quotes(50, 52)
    assert yes_cost == 0.50 and no_cost == 0.52
    assert abs(mid - 0.49) < 1e-9  # (0.50 + (1 - 0.52)) / 2


def test_quotes_treat_book_sentinels_as_absent():
    # 0 / 100 cent sentinels are not real quotes.
    assert _implied_yes_from_quotes(0, 100) == (None, None, None)


def test_yes_edge_flags_underpriced_yes():
    a = assess_mispricing("KXX", model_prob=0.70, yes_ask=50, no_ask=52)
    assert a.side == "YES"
    assert abs(a.edge - 0.20) < 1e-9  # 0.70 - 0.50
    assert a.agreement == "model_only" and a.confidence == "medium"


def test_no_edge_flags_underpriced_no():
    a = assess_mispricing("KXX", model_prob=0.30, yes_ask=55, no_ask=48)
    assert a.side == "NO"
    assert abs(a.edge - 0.22) < 1e-9  # (1 - 0.30) - 0.48


def test_no_actionable_edge_returns_none_side():
    a = assess_mispricing("KXX", model_prob=0.50, yes_ask=50, no_ask=52)
    assert a.side == "NONE"
    assert a.edge == 0.0
    assert a.agreement == "none"


def test_missing_quotes_fail_closed():
    a = assess_mispricing("KXX", model_prob=0.80, yes_ask=None, no_ask=None)
    assert a.side == "NONE"
    assert "no executable quote" in a.rationale


def test_book_confirmation_is_high_confidence():
    # Model likes YES; the sharp book also has YES well above the market mid.
    a = assess_mispricing("KXX", model_prob=0.70, yes_ask=50, no_ask=52, book_prob=0.68)
    assert a.side == "YES"
    assert a.agreement == "model+book" and a.confidence == "high"


def test_book_conflict_is_low_confidence():
    # Model likes YES but the sharp book prices YES BELOW the market mid.
    a = assess_mispricing("KXX", model_prob=0.70, yes_ask=50, no_ask=52, book_prob=0.40)
    assert a.side == "YES"
    assert a.agreement == "conflict" and a.confidence == "low"
    assert "CONFLICTS" in a.rationale


def test_book_neutral_is_medium_confidence():
    # Book sits at the market mid -> neither confirms nor denies.
    a = assess_mispricing("KXX", model_prob=0.70, yes_ask=50, no_ask=52, book_prob=0.50)
    assert a.side == "YES"
    assert a.agreement == "model_only" and a.confidence == "medium"


def test_no_side_book_confirmation():
    # Model likes NO (YES overpriced); book agrees YES is too high.
    a = assess_mispricing("KXX", model_prob=0.30, yes_ask=55, no_ask=48, book_prob=0.32)
    assert a.side == "NO"
    assert a.agreement == "model+book" and a.confidence == "high"


def test_no_side_book_conflict():
    # Model likes NO but the book prices YES even higher than the market.
    a = assess_mispricing("KXX", model_prob=0.30, yes_ask=55, no_ask=48, book_prob=0.70)
    assert a.side == "NO"
    assert a.agreement == "conflict" and a.confidence == "low"


def test_model_prob_is_clamped_and_result_is_frozen():
    a = assess_mispricing("KXX", model_prob=1.4, yes_ask=50, no_ask=52)
    assert a.model_prob == 1.0
    assert isinstance(a, MispricingAssessment)
    try:
        a.side = "NO"  # frozen dataclass
        raise AssertionError("assessment should be immutable")
    except AttributeError:
        pass


def test_deterministic():
    kwargs = dict(model_prob=0.63, yes_ask=48, no_ask=55, book_prob=0.60)
    assert assess_mispricing("KXX", **kwargs) == assess_mispricing("KXX", **kwargs)


def test_edge_threshold_is_respected():
    # A 3-cent edge is below the 4% default -> not actionable; a custom lower
    # threshold makes it actionable.
    assert assess_mispricing("KXX", model_prob=0.53, yes_ask=50, no_ask=52).side == "NONE"
    hit = assess_mispricing("KXX", model_prob=0.53, yes_ask=50, no_ask=52, edge_threshold=0.02)
    assert hit.side == "YES"


# --- MispricingMonitor ----------------------------------------------------

def test_monitor_shortlists_and_sorts_by_edge():
    markets = [
        _mkt("A", 50, 52),   # model 0.60 -> +0.10 edge
        _mkt("B", 30, 72),   # model 0.60 -> +0.30 edge (richest)
        _mkt("C", 50, 52),   # model 0.50 -> no edge
    ]
    probs = {"A": 0.60, "B": 0.60, "C": 0.50}
    monitor = MispricingMonitor(forecast_fn=lambda m: probs[m.ticker])
    out = monitor.scan(markets)
    assert [a.market_ticker for a in out] == ["B", "A"]  # C dropped, richest first


def test_monitor_skips_markets_with_no_model_view():
    monitor = MispricingMonitor(forecast_fn=lambda m: None)
    assert monitor.scan([_mkt("A", 50, 52)]) == []


def test_monitor_excludes_book_conflicts_even_with_big_edge():
    # Huge model edge on YES, but the sharp book says YES is overpriced.
    monitor = MispricingMonitor(
        forecast_fn=lambda m: 0.85, book_fn=lambda m: 0.30, min_confidence="low")
    assert monitor.scan([_mkt("A", 40, 62)]) == []


def test_monitor_min_confidence_high_requires_book_confirmation():
    markets = [_mkt("A", 50, 52)]
    # No book -> model_only (medium); high bar excludes it.
    no_book = MispricingMonitor(forecast_fn=lambda m: 0.70, min_confidence="high")
    assert no_book.scan(markets) == []
    # Book confirmation -> high; passes.
    confirmed = MispricingMonitor(
        forecast_fn=lambda m: 0.70, book_fn=lambda m: 0.68, min_confidence="high")
    hits = confirmed.scan(markets)
    assert len(hits) == 1 and hits[0].confidence == "high"


def test_monitor_book_fn_failure_degrades_to_model_only():
    def boom(_m):
        raise RuntimeError("book feed down")
    monitor = MispricingMonitor(forecast_fn=lambda m: 0.70, book_fn=boom)
    hits = monitor.scan([_mkt("A", 50, 52)])
    assert len(hits) == 1 and hits[0].agreement == "model_only"


def test_monitor_forecast_failure_is_fail_closed():
    def boom(_m):
        raise RuntimeError("model exploded")
    monitor = MispricingMonitor(forecast_fn=boom)
    assert monitor.scan([_mkt("A", 50, 52)]) == []


def test_monitor_works_for_crypto_without_a_book():
    # No book_fn at all (crypto): still shortlists on model edge.
    monitor = MispricingMonitor(forecast_fn=lambda m: 0.72)
    hits = monitor.scan([_mkt("KXBTC", 55, 47)])
    assert len(hits) == 1 and hits[0].book_prob is None
