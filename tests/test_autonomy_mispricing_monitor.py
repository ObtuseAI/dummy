"""Tests for the mispricing sweep (P2b orchestration)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

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


def test_sweep_does_not_fabricate_structural_from_both_sides_spread_markets():
    # End-to-end guard: ONE MLB game scanned with BOTH sides' spread markets
    # (HOU covers 1.5 AND TEX covers 1.5) at near-complementary prices. A
    # subject-blind ladder read these as a -0.30 rung inversion and stamped
    # every ticker structural. Must now produce ZERO structural violations.
    hou = _sports_market(
        "KXMLBSPREAD-26JUL132005HOUTEX-HOU2", "Houston wins by over 1.5 runs?", 25, 75,
        floor_strike=1.5,
    )
    tex = _sports_market(
        "KXMLBSPREAD-26JUL132005HOUTEX-TEX2", "Texas wins by over 1.5 runs?", 55, 45,
        floor_strike=1.5,
    )
    report = run_mispricing_sweep([hou, tex], lambda m: 0.50, now_iso=NOW)
    assert report["structural_count"] == 0
    assert len(report["lattices"]) == 1
    row = report["lattices"][0]
    assert row["cell_count"] == 2
    assert row["conviction_tier"] != "structural"
    assert row["ladder_violations"] == []


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


# --------------------------------------------------------------------------
# WS-8: book tape + paper-entry persistence (§3.2 CLV grading). The sweep
# stays pure -- these are new report keys the runner (or a test) can persist
# with autonomy.clv's tape/entry helpers; run_mispricing_sweep itself does
# no I/O.
# --------------------------------------------------------------------------

def test_sweep_emits_one_tape_row_per_assessed_market():
    winner = _sports_market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?", 50, 50,
    )
    report = run_mispricing_sweep(
        [winner], lambda m: 0.60, now_iso=NOW, book_fn=lambda m: 0.65,
    )
    assert len(report["tape_rows"]) == 1
    row = report["tape_rows"][0]
    assert row["ticker"] == winner.ticker
    assert row["ts"] == NOW
    assert row["book_prob"] == pytest.approx(0.65)
    assert row["close_time"] == winner.close_time
    assert row["kalshi_mid"] is not None  # mid implied by the 50/50 quotes


def test_sweep_tape_rows_cover_non_shortlisted_markets_too():
    # C has no edge (never shortlisted) but is still assessed -- the tape
    # must still capture it; CLV needs the full assessed universe, not just
    # the actionable subset.
    markets = [_mkt("A", 30, 72), _mkt("C", 50, 52)]
    probs = {"A": 0.70, "C": 0.50}
    report = run_mispricing_sweep(markets, lambda m: probs[m.ticker], now_iso=NOW)
    assert {row["ticker"] for row in report["tape_rows"]} == {"A", "C"}


def test_sweep_emits_entries_for_shortlist_and_opportunities():
    winner = _sports_market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?", 50, 50,
    )
    report = run_mispricing_sweep(
        [winner], lambda m: 0.65, now_iso=NOW, book_fn=lambda m: 0.68,
        min_confidence="low",
    )
    assert len(report["entries"]) >= 1
    entry = next(e for e in report["entries"] if e["ticker"] == winner.ticker)
    assert entry["side"] in ("YES", "NO")
    assert entry["entry_kalshi_prob"] is not None
    assert entry["market_type"] == "winner"  # from the KXMLBGAME series token


def test_sweep_entry_market_type_reads_the_series_token():
    spread = _sports_market(
        "KXMLBSPREAD-26JUL102005HOUTEX-HOU5", "Houston vs Texas Spread?", 45, 55,
        floor_strike=1.5,
    )
    report = run_mispricing_sweep(
        [spread], lambda m: 0.65, now_iso=NOW, book_fn=lambda m: 0.68,
        min_confidence="low",
    )
    entry = next(e for e in report["entries"] if e["ticker"] == spread.ticker)
    assert entry["market_type"] == "spread"


def test_sweep_entries_tagged_with_specialist_fn_source():
    winner = _sports_market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?", 50, 50,
    )
    report = run_mispricing_sweep(
        [winner], lambda m: 0.65, now_iso=NOW, book_fn=lambda m: 0.68,
        min_confidence="low", specialist_fn=lambda m: "mlb",
    )
    entry = next(e for e in report["entries"] if e["ticker"] == winner.ticker)
    assert entry["source"] == "mlb"


def test_sweep_entries_source_falls_back_to_unknown_without_specialist_fn():
    report = run_mispricing_sweep(
        [_mkt("A", 30, 72)], lambda m: 0.70, now_iso=NOW,
    )
    if report["entries"]:
        assert report["entries"][0]["source"] == "unknown"


def test_sweep_entries_and_tape_rows_are_json_serializable():
    import json

    winner = _sports_market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?", 50, 50,
    )
    report = run_mispricing_sweep(
        [winner], lambda m: 0.65, now_iso=NOW, book_fn=lambda m: 0.68,
        min_confidence="low", specialist_fn=lambda m: "mlb",
    )
    json.dumps(report)  # must not raise


def test_sweep_specialist_fn_exception_does_not_break_the_pass():
    def _boom(market):
        raise RuntimeError("no route")

    report = run_mispricing_sweep(
        [_mkt("A", 30, 72)], lambda m: 0.70, now_iso=NOW, specialist_fn=_boom,
    )
    assert report["assessed"] == 1  # the pass completes despite the routing error


# -- persistence: book tape + paper entries (autonomy.clv-backed I/O) ----------

def test_persist_book_tape_writes_and_dedups_across_calls(tmp_path):
    from autonomy.mispricing_monitor import persist_book_tape

    path = tmp_path / "book_tape.jsonl"
    winner = _sports_market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?", 50, 50,
    )
    report1 = run_mispricing_sweep(
        [winner], lambda m: 0.60, now_iso=NOW, book_fn=lambda m: 0.65,
    )
    last = persist_book_tape(path, report1)
    report2 = run_mispricing_sweep(  # identical prices -> same tape row
        [winner], lambda m: 0.60, now_iso="2026-07-12T00:01:30+00:00",
        book_fn=lambda m: 0.65,
    )
    persist_book_tape(path, report2, last_by_ticker=last)
    from autonomy.clv import load_tape_rows

    written = load_tape_rows(path)
    assert len(written) == 1  # second pass deduped -- book/kalshi unchanged


def test_persist_paper_entries_appends_jsonl(tmp_path):
    from autonomy.mispricing_monitor import persist_paper_entries

    path = tmp_path / "paper_entries.jsonl"
    winner = _sports_market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?", 50, 50,
    )
    report = run_mispricing_sweep(
        [winner], lambda m: 0.65, now_iso=NOW, book_fn=lambda m: 0.68,
        min_confidence="low",
    )
    written = persist_paper_entries(path, report)
    assert written == len(report["entries"])
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == written


def test_persist_paper_entries_no_entries_is_a_noop(tmp_path):
    from autonomy.mispricing_monitor import persist_paper_entries

    path = tmp_path / "paper_entries.jsonl"
    report = run_mispricing_sweep([_mkt("A", 50, 52)], lambda m: 0.50, now_iso=NOW)
    written = persist_paper_entries(path, report)
    assert written == 0
    assert not path.exists()
