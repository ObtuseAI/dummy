"""Tests for the patience / opportunist engine."""
from __future__ import annotations

from autonomy.mispricing import MispricingAssessment
from autonomy.opportunist import OpportunistEngine, _favored


def _assess(
    ticker="G", *, model_prob, market_prob, side="NONE", edge=0.0,
    agreement="model_only", confidence="medium", book_prob=None,
    conviction_tier=None,
) -> MispricingAssessment:
    return MispricingAssessment(
        market_ticker=ticker, side=side, model_prob=model_prob,
        market_prob=market_prob, book_prob=book_prob, edge=edge,
        agreement=agreement, confidence=confidence, rationale="test",
        conviction_tier=conviction_tier,
    )


def test_favored_side_and_conviction():
    assert _favored(0.75) == ("YES", 0.75)
    assert _favored(0.25) == ("NO", 0.75)


def test_locks_then_pounces_on_the_dip():
    eng = OpportunistEngine()
    # Lock a strong YES favorite at an efficient anchor (0.70) -> no strike yet.
    assert eng.observe(_assess(model_prob=0.75, market_prob=0.70, side="YES", edge=0.03)) is None
    # Early-game dip: price falls to 0.60, opening a 12% edge -> pounce.
    opp = eng.observe(_assess(model_prob=0.75, market_prob=0.60, side="YES", edge=0.12))
    assert opp is not None
    assert opp.side == "YES"
    assert abs(opp.deviation - 0.10) < 1e-9  # 0.70 -> 0.60
    assert opp.entry_prob == 0.60 and opp.conviction == 0.75


def test_patience_no_strike_at_the_anchor():
    eng = OpportunistEngine()
    # Even if the very first sighting already shows a big edge, we lock, not fire.
    assert eng.observe(_assess(model_prob=0.75, market_prob=0.55, side="YES", edge=0.20)) is None
    assert "G" in eng.candidates and not eng.candidates["G"].triggered


def test_small_deviation_does_not_trigger():
    eng = OpportunistEngine()
    eng.observe(_assess(model_prob=0.75, market_prob=0.70, side="YES", edge=0.03))
    # Big edge but the price barely moved from the anchor (0.70 -> 0.69).
    assert eng.observe(_assess(model_prob=0.75, market_prob=0.69, side="YES", edge=0.12)) is None


def test_book_conflict_never_pounces():
    # min_confidence="low" so the confidence gate would PASS -> only the explicit
    # conflict guard can block the fire, pinning that guard independently.
    eng = OpportunistEngine(min_confidence="low")
    eng.observe(_assess(model_prob=0.75, market_prob=0.70, side="YES", edge=0.03))
    assert eng.observe(_assess(
        model_prob=0.75, market_prob=0.58, side="YES", edge=0.15,
        agreement="conflict", confidence="medium")) is None


def test_never_fires_when_value_is_on_the_other_side():
    # Locked YES-favored; a qualifying dip whose actionable side is NOT our
    # locked side must not fire (pins the side-match guard).
    eng = OpportunistEngine()
    eng.observe(_assess(model_prob=0.75, market_prob=0.70, side="YES", edge=0.03))
    assert eng.observe(_assess(
        model_prob=0.75, market_prob=0.60, side="NONE", edge=0.12)) is None
    assert eng.observe(_assess(
        model_prob=0.75, market_prob=0.60, side="NO", edge=0.12)) is None


def test_low_conviction_never_locks():
    eng = OpportunistEngine()
    eng.observe(_assess(model_prob=0.55, market_prob=0.52, side="YES", edge=0.03))
    assert "G" not in eng.candidates
    assert eng.observe(_assess(model_prob=0.55, market_prob=0.40, side="YES", edge=0.12)) is None


def test_fires_at_most_once():
    eng = OpportunistEngine()
    eng.observe(_assess(model_prob=0.75, market_prob=0.70, side="YES", edge=0.03))
    first = eng.observe(_assess(model_prob=0.75, market_prob=0.60, side="YES", edge=0.12))
    second = eng.observe(_assess(model_prob=0.75, market_prob=0.58, side="YES", edge=0.15))
    assert first is not None and second is None


def test_no_side_favorite_pounces_when_yes_price_rises():
    eng = OpportunistEngine()
    # Model backs NO (model_prob 0.25 -> conviction 0.75); anchor YES prob 0.30.
    assert eng.observe(_assess(model_prob=0.25, market_prob=0.30, side="NO", edge=0.03)) is None
    # YES price rises to 0.45 (NO gets cheaper) -> deviation against NO... i.e. FOR
    # buying NO -> pounce.
    opp = eng.observe(_assess(model_prob=0.25, market_prob=0.45, side="NO", edge=0.10))
    assert opp is not None and opp.side == "NO"
    assert abs(opp.deviation - 0.15) < 1e-9  # 0.45 - 0.30


def test_min_confidence_gate():
    locked = _assess(model_prob=0.75, market_prob=0.70, side="YES", edge=0.03)
    dip_medium = _assess(model_prob=0.75, market_prob=0.60, side="YES", edge=0.12, confidence="medium")
    dip_high = _assess(
        model_prob=0.75, market_prob=0.60, side="YES", edge=0.12,
        agreement="model+book", confidence="high", book_prob=0.74)

    strict = OpportunistEngine(min_confidence="high")
    strict.observe(locked)
    assert strict.observe(dip_medium) is None      # medium below the bar
    strict2 = OpportunistEngine(min_confidence="high")
    strict2.observe(locked)
    assert strict2.observe(dip_high) is not None    # high clears it


def test_missing_market_price_is_fail_closed():
    eng = OpportunistEngine()
    assert eng.observe(_assess(model_prob=0.80, market_prob=None)) is None
    assert eng.candidates == {}


# --------------------------------------------------------------------------
# WS-5: conviction_tier drops the lock-in anchor threshold for structural /
# cross_confirmed lattice tiers. Absent tier (None, the default) must be
# byte-identical to today's behavior.
# --------------------------------------------------------------------------

def test_conviction_tier_absent_is_byte_identical_to_today():
    eng = OpportunistEngine()
    # Below the 0.62 floor and no tier -> still refuses to lock, same as today.
    assert eng.observe(_assess(model_prob=0.58, market_prob=0.55, side="YES", edge=0.03)) is None
    assert eng.candidates == {}


def test_structural_tier_drops_anchor_threshold_by_0_04():
    eng = OpportunistEngine()
    # model_prob=0.59 -> conviction 0.59; floor 0.62 - 0.04 = 0.58 -> clears.
    opp = eng.observe(_assess(
        model_prob=0.59, market_prob=0.55, side="YES", edge=0.03,
        conviction_tier="structural",
    ))
    assert opp is None  # lock-in observation never fires immediately
    assert "G" in eng.candidates and eng.candidates["G"].conviction == 0.59


def test_structural_tier_still_refuses_below_the_dropped_floor():
    eng = OpportunistEngine()
    # conviction 0.55 is still below 0.62 - 0.04 = 0.58 -> refuses even with the tier.
    assert eng.observe(_assess(
        model_prob=0.55, market_prob=0.55, side="YES", edge=0.03,
        conviction_tier="structural",
    )) is None
    assert eng.candidates == {}


def test_cross_confirmed_tier_drops_anchor_threshold_by_0_02():
    eng = OpportunistEngine()
    # model_prob=0.61 -> conviction 0.61; floor 0.62 - 0.02 = 0.60 -> clears.
    eng.observe(_assess(
        model_prob=0.61, market_prob=0.55, side="YES", edge=0.03,
        conviction_tier="cross_confirmed",
    ))
    assert "G" in eng.candidates


def test_cross_confirmed_tier_does_not_clear_the_structural_sized_gap():
    eng = OpportunistEngine()
    # conviction 0.59 clears the structural-dropped floor (0.58) but not the
    # smaller cross_confirmed drop (0.62 - 0.02 = 0.60).
    assert eng.observe(_assess(
        model_prob=0.59, market_prob=0.55, side="YES", edge=0.03,
        conviction_tier="cross_confirmed",
    )) is None
    assert eng.candidates == {}


def test_unknown_conviction_tier_is_treated_as_no_drop():
    eng = OpportunistEngine()
    assert eng.observe(_assess(
        model_prob=0.59, market_prob=0.55, side="YES", edge=0.03,
        conviction_tier="some_future_tier",
    )) is None
    assert eng.candidates == {}
