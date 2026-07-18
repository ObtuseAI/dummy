"""Wave-14: picks-first accuracy layer (fused row + outcome-grounded grading)."""
from __future__ import annotations

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Forecast, Signal
from autonomy.picks import (
    FUSED_SOURCE,
    build_fused_signal,
    grade_picks,
    grade_source_picks,
    latest_settled_emissions,
    pick_accuracy_report,
)


def _forecast(p=0.62, ticker="KXMLBGAME-26JUL17NYYBOS-NYY"):
    return Forecast(
        market_ticker=ticker, probability_yes=p, uncertainty=0.12,
        sources_used={"mlb_intelligence": 1.4, "sportsbook_consensus": 1.1},
        market_implied_yes=0.55, edge_yes=p - 0.55, rationale="test fuse")


def _emit(ledger, ticker, p, source=FUSED_SOURCE, when="2026-07-17T18:00:00+00:00"):
    ledger.record_signal(Signal(
        source=source, market_ticker=ticker, probability_yes=p,
        uncertainty=0.1, rationale="r", created_at=when,
        features={"challenger_only": False}))


def test_build_fused_signal_is_output_not_candidate():
    signal = build_fused_signal("KXMLBGAME-26JUL17NYYBOS-NYY", _forecast())
    assert signal.source == FUSED_SOURCE
    assert signal.probability_yes == 0.62
    assert signal.features["challenger_only"] is False
    assert signal.features["is_fused_output"] is True
    assert signal.features["sources_used"]["mlb_intelligence"] == 1.4


def test_grade_picks_hit_rate_brier_and_no_pick_band():
    emissions = [
        ("T1", 0.70, True),    # pick yes, hit
        ("T2", 0.80, False),   # pick yes, miss
        ("T3", 0.30, False),   # pick no, hit
        ("T4", 0.505, True),   # inside no-pick band: Brier only
    ]
    graded = grade_picks(emissions)
    assert graded["n"] == 4
    assert graded["picks"] == 3 and graded["no_pick"] == 1
    assert graded["hit_rate"] == round(2 / 3, 4)
    expected_brier = (0.09 + 0.64 + 0.09 + 0.245025) / 4
    assert abs(graded["brier"] - expected_brier) < 1e-4
    assert any(b["n"] for b in graded["calibration"])


def test_latest_emission_is_the_pick_of_record(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    ticker = "KXMLBGAME-26JUL17NYYBOS-NYY"
    _emit(ledger, ticker, 0.40, when="2026-07-17T15:00:00+00:00")
    _emit(ledger, ticker, 0.65, when="2026-07-17T18:30:00+00:00")   # final opinion
    ledger.record_settlement(ticker, True)
    rows = latest_settled_emissions(ledger._conn, FUSED_SOURCE)
    assert rows == [(ticker, 0.65, True)]
    graded = grade_source_picks(ledger._conn, days=None)
    assert graded["overall"]["n"] == 1
    assert graded["overall"]["hit_rate"] == 1.0


def test_scope_breakdown_uses_the_series_registry(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    for i in range(6):
        ticker = f"KXMLBGAME-26JUL1{i}AAABBB-AAA"
        _emit(ledger, ticker, 0.70, when=f"2026-07-1{i}T18:00:00+00:00")
        ledger.record_settlement(ticker, True)
    for i in range(6):
        ticker = f"KXWNBATOTAL-26JUL1{i}CCCDDD-T160"
        _emit(ledger, ticker, 0.30, when=f"2026-07-1{i}T18:00:00+00:00")
        ledger.record_settlement(ticker, False)
    graded = grade_source_picks(ledger._conn, days=None)
    assert graded["overall"]["n"] == 12
    assert graded["by_scope"]["mlb|winner"]["hit_rate"] == 1.0
    assert graded["by_scope"]["wnba|total"]["hit_rate"] == 1.0


def test_report_shape_and_taxonomy_home(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    report = pick_accuracy_report(ledger._conn)
    assert report["sources"][0]["source"] == FUSED_SOURCE
    assert report["sources"][0]["overall"] == {"n": 0}

    from autonomy.taxonomy import specialist_for

    assert specialist_for(FUSED_SOURCE) == "fused"
