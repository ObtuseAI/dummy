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


def _insert_raw_emission(conn, ticker, p, created_at, ingested_at, *, mode="live"):
    conn.execute(
        "INSERT INTO signals (source, market_ticker, probability_yes, uncertainty,"
        " rationale, features, created_at, mode, ingested_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (
            FUSED_SOURCE,
            ticker,
            p,
            0.1,
            "r",
            '{"challenger_only": false}',
            created_at,
            mode,
            ingested_at,
        ),
    )


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


def test_pick_of_record_excludes_retro_late_and_post_decision_rows(tmp_path):
    ledger = AutonomyLedger(tmp_path / "pit-picks.db")
    ticker = "KXMLBGAME-26JUL17NYYBOS-NYY"
    try:
        _insert_raw_emission(
            ledger._conn,
            ticker,
            0.65,
            "2026-07-17T18:00:00+00:00",
            "2026-07-17T18:01:00+00:00",
        )
        _insert_raw_emission(
            ledger._conn,
            ticker,
            0.20,
            "2026-07-17T18:30:00+00:00",
            "2026-07-17T18:31:00+00:00",
            mode="retro",
        )
        _insert_raw_emission(
            ledger._conn,
            ticker,
            0.10,
            "2026-07-17T18:45:00+00:00",
            "2026-07-17T20:01:00+00:00",
        )
        _insert_raw_emission(
            ledger._conn,
            ticker,
            0.95,
            "2026-07-17T19:05:00+00:00",
            "2026-07-17T19:06:00+00:00",
        )
        ledger._conn.execute(
            "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
            " VALUES (?,?,?)",
            (ticker, 1, "2026-07-17T20:00:00+00:00"),
        )
        ledger._conn.execute(
            "INSERT INTO decisions (decision_id, market_ticker, action, side,"
            " price_cents, count, ev_cents, kelly, notional_cents,"
            " probability_yes, forecast_uncertainty, market_implied_yes,"
            " sources_used, abstain_reason, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "d-pit",
                ticker,
                "abstain",
                "yes",
                50,
                0,
                0.0,
                0.0,
                0,
                0.65,
                0.1,
                0.5,
                "{}",
                "test",
                "2026-07-17T19:00:00+00:00",
            ),
        )
        ledger._conn.commit()

        assert latest_settled_emissions(
            ledger._conn, FUSED_SOURCE, days=None,
        ) == [(ticker, 0.65, True)]
    finally:
        ledger.close()


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
