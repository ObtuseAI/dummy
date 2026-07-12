"""Tests for the mispricing sweep (P2b orchestration)."""
from __future__ import annotations

from types import SimpleNamespace

from autonomy.mispricing_monitor import run_mispricing_sweep
from autonomy.opportunist import OpportunistEngine

NOW = "2026-07-12T00:00:00+00:00"


def _mkt(ticker, yes_ask, no_ask):
    return SimpleNamespace(ticker=ticker, yes_ask=yes_ask, no_ask=no_ask)


def test_sweep_reports_shortlist_richest_first():
    markets = [_mkt("A", 50, 52), _mkt("B", 30, 72), _mkt("C", 50, 52)]
    probs = {"A": 0.60, "B": 0.60, "C": 0.50}
    report = run_mispricing_sweep(markets, lambda m: probs[m.ticker], now_iso=NOW)
    assert report["scanned"] == 3
    assert report["assessed"] == 3
    tickers = [row["ticker"] for row in report["shortlist"]]
    assert tickers == ["B", "A"]  # C has no edge; B's edge > A's
    assert report["shortlist"][0]["edge"] >= report["shortlist"][1]["edge"]


def test_sweep_skips_markets_without_a_model_view():
    report = run_mispricing_sweep([_mkt("A", 50, 52)], lambda m: None, now_iso=NOW)
    assert report["scanned"] == 1 and report["assessed"] == 0
    assert report["shortlist"] == []


def test_sweep_excludes_conflicts_from_shortlist():
    report = run_mispricing_sweep(
        [_mkt("A", 40, 62)], lambda m: 0.85, now_iso=NOW,
        book_fn=lambda m: 0.30, min_confidence="low",
    )
    assert report["shortlist"] == []  # model+book conflict never shortlisted


def test_sweep_caps_shortlist_to_max_items():
    markets = [_mkt(f"M{i}", 30, 72) for i in range(10)]
    report = run_mispricing_sweep(markets, lambda m: 0.70, now_iso=NOW, max_items=3)
    assert len(report["shortlist"]) == 3
    assert report["shortlist_count"] == 10  # full count preserved in the summary


def test_sweep_drives_the_opportunist_across_passes():
    engine = OpportunistEngine()
    markets = [_mkt("G", 50, 52)]  # anchor mid 0.49
    # Pass 1: lock a strong favorite (model 0.75); no strike yet.
    r1 = run_mispricing_sweep(markets, lambda m: 0.75, now_iso=NOW, opportunist=engine)
    assert r1["opportunity_count"] == 0
    assert "G" in engine.candidates
    # Pass 2: price dips (YES ask 40 -> mid ~0.39), opening the edge -> pounce.
    r2 = run_mispricing_sweep(
        [_mkt("G", 40, 62)], lambda m: 0.75, now_iso=NOW, opportunist=engine)
    assert r2["opportunity_count"] == 1
    assert r2["opportunities"][0]["ticker"] == "G"
    assert r2["opportunities"][0]["side"] == "YES"


def test_sweep_report_is_json_serializable():
    import json
    report = run_mispricing_sweep([_mkt("A", 30, 72)], lambda m: 0.70, now_iso=NOW)
    text = json.dumps(report)  # must not raise
    assert '"generated_at"' in text and '"shortlist"' in text
