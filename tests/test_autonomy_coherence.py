"""Tests for the WS-5 3x3 conviction lattice + coherence engine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.coherence import (
    FEE_BAND,
    GameLattice,
    LatticeCell,
    TIER_CROSS_CONFIRMED,
    TIER_MODEL_BOOK,
    TIER_MODEL_ONLY,
    TIER_STRUCTURAL,
    build_game_lattices,
    cross_family_incoherence,
    ladder_violations,
    lattice_conviction,
)
from autonomy.mispricing import MispricingAssessment
from autonomy.ontology import MarketView, Vertical

NOW = datetime(2026, 7, 10, tzinfo=timezone.utc)


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(days=2)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


def _cell(family, ticker, line, model_prob, book_prob, kalshi_prob):
    return LatticeCell(
        family=family, ticker=ticker, line=line,
        model_prob=model_prob, book_prob=book_prob, kalshi_prob=kalshi_prob,
    )


def _assessment(ticker, *, side, model_prob, market_prob, agreement, confidence="high", book_prob=None, edge=0.1):
    return MispricingAssessment(
        market_ticker=ticker, side=side, model_prob=model_prob,
        market_prob=market_prob, book_prob=book_prob, edge=edge,
        agreement=agreement, confidence=confidence, rationale="test",
    )


# --------------------------------------------------------------------------
# ladder_violations
# --------------------------------------------------------------------------

def test_ladder_violations_flags_planted_rung_inversion():
    cells = [
        _cell("spread", "S1", 1.5, None, None, 0.60),
        _cell("spread", "S2", 2.5, None, None, 0.35),
        _cell("spread", "S3", 3.5, None, None, 0.50),  # planted inversion vs S2
    ]
    violations = ladder_violations(cells, "spread")
    assert len(violations) == 1
    row = violations[0]
    assert row["rungs"] == (2.5, 3.5)
    assert row["tier"] == "structural"
    assert row["gap"] < -FEE_BAND


def test_ladder_violations_fee_band_suppresses_small_gap():
    # 1.5 -> 2.5 rises by 0.02, well inside the fee band -> no violation.
    cells = [
        _cell("spread", "S1", 1.5, None, None, 0.50),
        _cell("spread", "S2", 2.5, None, None, 0.52),
    ]
    assert ladder_violations(cells, "spread") == []


def test_ladder_violations_just_inside_the_fee_band_is_not_a_violation():
    # Rise of 0.029 (< FEE_BAND=0.03 slack) must NOT count; strict inequality
    # at the exact boundary is a float-precision trap, so stay a hair inside.
    cells = [
        _cell("spread", "S1", 1.5, None, None, 0.50),
        _cell("spread", "S2", 2.5, None, None, 0.529),
    ]
    assert ladder_violations(cells, "spread") == []


def test_ladder_violations_just_outside_the_fee_band_is_a_violation():
    # Rise of 0.031 (> FEE_BAND=0.03 slack) must count.
    cells = [
        _cell("spread", "S1", 1.5, None, None, 0.50),
        _cell("spread", "S2", 2.5, None, None, 0.531),
    ]
    assert len(ladder_violations(cells, "spread")) == 1


def test_ladder_violations_ignores_other_family_and_missing_lines():
    cells = [
        _cell("spread", "S1", 1.5, None, None, 0.60),
        _cell("total", "T1", 8.5, None, None, 0.10),   # different family, ignored
        _cell("spread", "S2", None, None, None, 0.90),  # no line, ignored
        _cell("spread", "S3", 2.5, None, None, 0.35),
    ]
    # Only S1 (1.5) vs S3 (2.5) form a real spread ladder pair; monotone, no violation.
    assert ladder_violations(cells, "spread") == []


def test_ladder_violations_needs_at_least_two_rungs():
    assert ladder_violations([_cell("spread", "S1", 1.5, None, None, 0.6)], "spread") == []
    assert ladder_violations([], "spread") == []


# --------------------------------------------------------------------------
# cross_family_incoherence
# --------------------------------------------------------------------------

def test_cross_family_incoherence_hand_computed_gap():
    # model_win=0.65, model_cover(k)=0.55, kalshi_cover(k)=0.55, kalshi_winner=0.50
    # implied_win = 0.65 - 0.55 + 0.55 = 0.65; gap = 0.50 - 0.65 = -0.15
    # |gap| = 0.15 > 2*FEE_BAND (0.06) -> a row.
    lattice = GameLattice(
        game_key="mlb:20260710:HOU@TEX", sport="mlb",
        cells=[
            _cell("winner", "W1", None, 0.65, None, 0.50),
            _cell("spread", "S1", 1.5, 0.55, None, 0.55),
        ],
    )
    rows = cross_family_incoherence(lattice)
    assert len(rows) == 1
    row = rows[0]
    assert row["line"] == 1.5
    assert abs(row["implied_win"] - 0.65) < 1e-9
    assert abs(row["gap"] - (-0.15)) < 1e-9
    assert row["game_key"] == "mlb:20260710:HOU@TEX"


def test_cross_family_incoherence_below_threshold_produces_no_row():
    # implied_win = 0.60 - 0.55 + 0.50 = 0.55; gap = 0.50 - 0.55 = -0.05
    # |gap| = 0.05 is NOT > 2*FEE_BAND (0.06) -> suppressed.
    lattice = GameLattice(
        game_key="mlb:20260710:HOU@TEX", sport="mlb",
        cells=[
            _cell("winner", "W1", None, 0.60, None, 0.50),
            _cell("spread", "S1", 1.5, 0.55, None, 0.50),
        ],
    )
    assert cross_family_incoherence(lattice) == []


def test_cross_family_incoherence_skips_pairs_missing_probabilities():
    lattice = GameLattice(
        game_key="mlb:20260710:HOU@TEX", sport="mlb",
        cells=[
            _cell("winner", "W1", None, None, None, 0.50),  # model_prob missing
            _cell("spread", "S1", 1.5, 0.55, None, None),   # kalshi_prob missing
        ],
    )
    assert cross_family_incoherence(lattice) == []


def test_cross_family_incoherence_only_pairs_winner_and_spread():
    lattice = GameLattice(
        game_key="mlb:20260710:HOU@TEX", sport="mlb",
        cells=[_cell("total", "T1", 8.5, 0.55, None, 0.10)],
    )
    assert cross_family_incoherence(lattice) == []


# --------------------------------------------------------------------------
# lattice_conviction
# --------------------------------------------------------------------------

def test_lattice_conviction_structural_beats_everything():
    lattice = GameLattice(
        game_key="g", sport="mlb",
        cells=[
            _cell("spread", "S1", 1.5, None, None, 0.60),
            _cell("spread", "S2", 2.5, None, None, 0.35),
            _cell("spread", "S3", 3.5, None, None, 0.50),  # inversion -> structural
        ],
    )
    assessments = {
        "S1": _assessment("S1", side="YES", model_prob=0.6, market_prob=0.6, agreement=TIER_MODEL_BOOK),
    }
    result = lattice_conviction(lattice, assessments)
    assert result["conviction_tier"] == TIER_STRUCTURAL
    assert result["game_key"] == "g"


def test_lattice_conviction_cross_confirmed_needs_two_families_same_side_book_agreement():
    lattice = GameLattice(
        game_key="g", sport="mlb",
        cells=[
            _cell("winner", "W1", None, 0.65, 0.68, 0.50),
            _cell("spread", "S1", 1.5, 0.60, 0.62, 0.45),
        ],
    )
    assessments = {
        "W1": _assessment("W1", side="YES", model_prob=0.65, market_prob=0.50, agreement=TIER_MODEL_BOOK, book_prob=0.68),
        "S1": _assessment("S1", side="YES", model_prob=0.60, market_prob=0.45, agreement=TIER_MODEL_BOOK, book_prob=0.62),
    }
    result = lattice_conviction(lattice, assessments)
    assert result["conviction_tier"] == TIER_CROSS_CONFIRMED


def test_lattice_conviction_opposite_sides_do_not_cross_confirm():
    lattice = GameLattice(
        game_key="g", sport="mlb",
        cells=[
            _cell("winner", "W1", None, 0.65, 0.68, 0.50),
            _cell("spread", "S1", 1.5, 0.40, 0.38, 0.45),
        ],
    )
    assessments = {
        "W1": _assessment("W1", side="YES", model_prob=0.65, market_prob=0.50, agreement=TIER_MODEL_BOOK, book_prob=0.68),
        "S1": _assessment("S1", side="NO", model_prob=0.40, market_prob=0.45, agreement=TIER_MODEL_BOOK, book_prob=0.38),
    }
    result = lattice_conviction(lattice, assessments)
    # Same tier count (book agreement) but opposite direction -> falls to model+book.
    assert result["conviction_tier"] == TIER_MODEL_BOOK


def test_lattice_conviction_model_plus_book_single_family():
    lattice = GameLattice(
        game_key="g", sport="mlb",
        cells=[_cell("winner", "W1", None, 0.65, 0.68, 0.50)],
    )
    assessments = {
        "W1": _assessment("W1", side="YES", model_prob=0.65, market_prob=0.50, agreement=TIER_MODEL_BOOK, book_prob=0.68),
    }
    assert lattice_conviction(lattice, assessments)["conviction_tier"] == TIER_MODEL_BOOK


def test_lattice_conviction_model_only_fallback():
    lattice = GameLattice(
        game_key="g", sport="mlb",
        cells=[_cell("winner", "W1", None, 0.65, None, 0.50)],
    )
    assessments = {
        "W1": _assessment("W1", side="YES", model_prob=0.65, market_prob=0.50, agreement="model_only"),
    }
    assert lattice_conviction(lattice, assessments)["conviction_tier"] == TIER_MODEL_ONLY


def test_lattice_conviction_none_when_no_actionable_cells():
    lattice = GameLattice(
        game_key="g", sport="mlb",
        cells=[_cell("winner", "W1", None, 0.50, None, 0.50)],
    )
    assessments = {
        "W1": _assessment("W1", side="NONE", model_prob=0.50, market_prob=0.50, agreement="none"),
    }
    assert lattice_conviction(lattice, assessments)["conviction_tier"] is None


def test_lattice_conviction_fails_closed_when_cell_ticker_missing_from_assessments():
    lattice = GameLattice(
        game_key="g", sport="mlb",
        cells=[_cell("winner", "W1", None, 0.65, None, 0.50)],
    )
    assert lattice_conviction(lattice, {})["conviction_tier"] is None


# --------------------------------------------------------------------------
# build_game_lattices -- THROUGH the real parse_sports_contract, not hand dicts
# --------------------------------------------------------------------------

def test_build_game_lattices_groups_two_real_mlb_markets_into_one_lattice():
    winner_market = _market(
        "KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?",
        yes_sub_title="Houston",
    )
    spread_market = _market(
        "KXMLBSPREAD-26JUL102005HOUTEX-HOU2", "Houston vs Texas Spread?",
        floor_strike=1.5, strike_type="greater",
    )
    assessments = {
        "KXMLBGAME-26JUL102005HOUTEX-HOU": _assessment(
            "KXMLBGAME-26JUL102005HOUTEX-HOU", side="YES", model_prob=0.65,
            market_prob=0.50, agreement=TIER_MODEL_BOOK, book_prob=0.68,
        ),
        "KXMLBSPREAD-26JUL102005HOUTEX-HOU2": _assessment(
            "KXMLBSPREAD-26JUL102005HOUTEX-HOU2", side="YES", model_prob=0.55,
            market_prob=0.45, agreement=TIER_MODEL_BOOK, book_prob=0.60,
        ),
    }
    lattices = build_game_lattices([winner_market, spread_market], assessments)
    assert len(lattices) == 1
    lattice = lattices[0]
    assert lattice.sport == "mlb"
    assert len(lattice.cells) == 2
    families = {c.family for c in lattice.cells}
    assert families == {"winner", "spread"}
    spread_cell = next(c for c in lattice.cells if c.family == "spread")
    assert spread_cell.line == 1.5
    # Cells carry the SAME already-computed assessment values -- no second fetch.
    winner_cell = next(c for c in lattice.cells if c.family == "winner")
    assert winner_cell.model_prob == 0.65
    assert winner_cell.kalshi_prob == 0.50
    assert winner_cell.book_prob == 0.68


def test_build_game_lattices_ignores_market_with_no_assessment():
    winner_market = _market("KXMLBGAME-26JUL102005HOUTEX-HOU", "Houston vs Texas Winner?")
    assert build_game_lattices([winner_market], {}) == []


def test_build_game_lattices_ignores_unparseable_market():
    market = _market("KXWEATHER-NYC-26JUL10", "NYC high temp?")
    assessments = {
        "KXWEATHER-NYC-26JUL10": _assessment(
            "KXWEATHER-NYC-26JUL10", side="YES", model_prob=0.5, market_prob=0.5, agreement="model_only",
        ),
    }
    assert build_game_lattices([market], assessments) == []


def test_build_game_lattices_ignores_yrfi_family_not_in_the_3x3():
    market = _market("KXMLBRFI-26JUL102005HOUTEX", "Houston vs Texas First Inning Run?")
    assessments = {
        "KXMLBRFI-26JUL102005HOUTEX": _assessment(
            "KXMLBRFI-26JUL102005HOUTEX", side="YES", model_prob=0.5, market_prob=0.5, agreement="model_only",
        ),
    }
    assert build_game_lattices([market], assessments) == []


def test_build_game_lattices_empty_input_yields_no_lattices():
    assert build_game_lattices([], {}) == []
