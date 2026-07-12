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


# --------------------------------------------------------------------------
# WS-5: the lattice section, assembled from the SAME markets/assessments the
# sweep already computes, THROUGH the real parse_sports_contract (not a
# hand-built dict). Non-sports markets never group -> byte-identical report.
# --------------------------------------------------------------------------

from autonomy.ontology import MarketView, Vertical  # noqa: E402


def _sports_market(ticker: str, title: str, yes_ask: int, no_ask: int, **raw) -> MarketView:
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time="2026-07-12T20:00:00+00:00",
        yes_bid=yes_ask - 2, yes_ask=yes_ask, no_bid=no_ask - 2, no_ask=no_ask,
        volume=500, liquidity=10_000, raw=raw,
    )


def test_sweep_lattice_section_is_empty_when_nothing_parses_as_sports():
    report = run_mispricing_sweep([_mkt("A", 30, 72)], lambda m: 0.70, now_iso=NOW)
    assert report["lattices"] == []
    assert report["structural_count"] == 0
    assert report["cross_confirmed_count"] == 0


def test_sweep_groups_two_real_mlb_markets_into_one_cross_confirmed_lattice():
    winner = _sports_market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?", 50, 50,
    )
    spread = _sports_market(
        "KXMLBSPREAD-26JUL102005HOUTEX-HOU5", "Houston vs Texas Spread?", 45, 55,
        floor_strike=1.5,
    )
    model = {winner.ticker: 0.65, spread.ticker: 0.60}
    book = {winner.ticker: 0.70, spread.ticker: 0.64}
    report = run_mispricing_sweep(
        [winner, spread], lambda m: model[m.ticker], now_iso=NOW,
        book_fn=lambda m: book[m.ticker], min_confidence="low",
    )
    assert report["structural_count"] == 0
    assert report["cross_confirmed_count"] == 1
    assert len(report["lattices"]) == 1
    row = report["lattices"][0]
    assert row["sport"] == "mlb"
    assert row["conviction_tier"] == "cross_confirmed"
    assert row["cell_count"] == 2


def test_sweep_flags_structural_ladder_inversion_across_three_spread_rungs():
    rung1 = _sports_market(
        "KXMLBSPREAD-26JUL112005HOUTEX-HOU2", "Houston vs Texas Spread?", 60, 40,
        floor_strike=1.5,
    )
    rung2 = _sports_market(
        "KXMLBSPREAD-26JUL112005HOUTEX-HOU3", "Houston vs Texas Spread?", 35, 65,
        floor_strike=2.5,
    )
    rung3 = _sports_market(  # planted inversion: cheaper-to-cover-more than rung2
        "KXMLBSPREAD-26JUL112005HOUTEX-HOU4", "Houston vs Texas Spread?", 50, 50,
        floor_strike=3.5,
    )
    report = run_mispricing_sweep(
        [rung1, rung2, rung3], lambda m: 0.50, now_iso=NOW,
    )
    assert report["structural_count"] == 1
    assert report["cross_confirmed_count"] == 0
    row = report["lattices"][0]
    assert row["conviction_tier"] == "structural"
    assert len(row["ladder_violations"]) == 1
    assert row["ladder_violations"][0]["game_key"] == row["game_key"]


def test_sweep_attaches_conviction_tier_to_lower_the_opportunist_anchor_floor():
    # Winner conviction 0.605 is below the default 0.62 floor but above the
    # cross_confirmed-dropped floor (0.62 - 0.02 = 0.60) -- proves the tier
    # actually reaches OpportunistEngine.observe, not just the report.
    winner = _sports_market(
        "KXMLBGAME-26JUL122005HOUTEX-HOU", "Houston vs Texas Winner?", 50, 50,
    )
    spread = _sports_market(
        "KXMLBSPREAD-26JUL122005HOUTEX-HOU5", "Houston vs Texas Spread?", 45, 55,
        floor_strike=1.5,
    )
    model = {winner.ticker: 0.605, spread.ticker: 0.60}
    book = {winner.ticker: 0.66, spread.ticker: 0.64}
    engine = OpportunistEngine()
    run_mispricing_sweep(
        [winner, spread], lambda m: model[m.ticker], now_iso=NOW,
        book_fn=lambda m: book[m.ticker], opportunist=engine, min_confidence="low",
    )
    assert winner.ticker in engine.candidates
    assert abs(engine.candidates[winner.ticker].conviction - 0.605) < 1e-9


def test_sweep_structural_count_reflects_all_games_not_just_the_capped_display():
    # 21 games each with a planted structural ladder violation -- one more
    # than the display cap (20). The COUNT must still be 21; only the
    # "lattices" display list is capped.
    markets = []
    for day in range(1, 22):
        rung1 = _sports_market(
            f"KXMLBSPREAD-26JUL{day:02d}2005HOUTEX-HOU2", "Houston vs Texas Spread?", 60, 40,
            floor_strike=1.5,
        )
        rung2 = _sports_market(
            f"KXMLBSPREAD-26JUL{day:02d}2005HOUTEX-HOU3", "Houston vs Texas Spread?", 90, 10,
            floor_strike=2.5,
        )
        markets += [rung1, rung2]
    report = run_mispricing_sweep(markets, lambda m: 0.50, now_iso=NOW)
    assert report["structural_count"] == 21
    assert len(report["lattices"]) == 20


def test_sweep_lattices_capped_at_twenty_games():
    markets = [
        _sports_market(
            f"KXMLBGAME-26JUL{day:02d}2005HOUTEX-HOU", "Houston vs Texas Winner?", 45, 55,
        )
        for day in range(1, 26)  # 25 distinct games
    ]
    report = run_mispricing_sweep(markets, lambda m: 0.55, now_iso=NOW)
    assert report["assessed"] == 25
    assert len(report["lattices"]) == 20
