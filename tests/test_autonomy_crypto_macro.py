"""Tests for the crypto macro-regime challenger signal."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_macro import (
    CryptoMacroRegimeSignal,
    macro_regime_score,
    _pct_change,
)


# --- pure helpers ---------------------------------------------------------

def test_pct_change_over_five_sessions():
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 110.0]  # 6 closes, 5 back = 100
    assert abs(_pct_change(closes, sessions=5) - 0.10) < 1e-9


def test_pct_change_insufficient_history_returns_none():
    assert _pct_change([100.0, 101.0], sessions=5) is None


def test_pct_change_skips_none_values():
    # 6 usable closes after dropping None: 110/100 - 1 = +10% over 5 sessions.
    closes = [None, 100.0, None, 101.0, 102.0, 103.0, 104.0, 110.0]
    assert abs(_pct_change(closes, sessions=5) - 0.10) < 1e-9


def test_macro_score_risk_on_is_positive():
    # Equities up, dollar down, vix down -> crypto risk-on -> positive score.
    score, coverage, _ = macro_regime_score(
        {"sp500": 0.03, "dxy": -0.02, "vix": -0.15}
    )
    assert score > 0.0
    assert 0.0 < coverage < 1.0  # only 3 of 6 factors present


def test_macro_score_risk_off_is_negative():
    # Equities down, dollar up, vix spiking -> risk-off -> negative score.
    score, _, _ = macro_regime_score({"sp500": -0.03, "dxy": 0.02, "vix": 0.30})
    assert score < 0.0


def test_macro_score_empty_is_zero_no_coverage():
    score, coverage, components = macro_regime_score({})
    assert score == 0.0
    assert coverage == 0.0
    assert components == {}


def test_macro_score_is_bounded_under_extreme_inputs():
    huge = {"sp500": 10.0, "dxy": -10.0, "vix": -10.0, "ust10y": -10.0,
            "gold": 10.0, "oil": 10.0}
    score, coverage, _ = macro_regime_score(huge)
    assert -1.0 <= score <= 1.0
    assert abs(coverage - 1.0) < 1e-9  # all six factors present


# --- signal behavior ------------------------------------------------------

def _crypto_market(ticker="KXBTCD-26JUL0917-T71000", strike_type="greater",
                   floor=71000.0, cap=None):
    raw = {"strike_type": strike_type}
    if floor is not None:
        raw["floor_strike"] = floor
    if cap is not None:
        raw["cap_strike"] = cap
    return MarketView(
        ticker=ticker, title="BTC above 71000", vertical=Vertical.CRYPTO, status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
        yes_bid=40, yes_ask=50, no_bid=50, no_ask=60, volume=100, liquidity=100, raw=raw,
    )


def _state(_asset):
    # Spot at the strike so the no-drift probability is ~0.5 and the macro
    # drift is the only thing that moves it off center.
    return {"spot": 71000.0, "dvol": 60.0}


def _signal(risk):
    if risk == "on":
        macro = {"sp500": 0.03, "dxy": -0.02, "vix": -0.15}
    elif risk == "off":
        macro = {"sp500": -0.03, "dxy": 0.02, "vix": 0.30}
    else:
        macro = {}
    return CryptoMacroRegimeSignal(
        fetch_state=_state,
        fetch_macro=lambda: macro,
        hours_to_close=lambda m: 12.0,
    )


def test_applicable_only_to_crypto():
    sig = _signal("on")
    assert sig.applicable(_crypto_market()) is True
    commodity = _crypto_market()
    commodity = MarketView(**{**commodity.__dict__, "vertical": Vertical.COMMODITIES})
    assert sig.applicable(commodity) is False


def test_risk_on_raises_probability_above_risk_off_for_above_market():
    market = _crypto_market(strike_type="greater", floor=71000.0)
    p_on = _signal("on").generate(market).probability_yes
    p_off = _signal("off").generate(market).probability_yes
    assert p_on > 0.5 > p_off  # spot==strike: drift is the only mover


def test_below_market_flips_the_macro_tilt():
    # A "less than cap" market should move OPPOSITE to an "above" market.
    above = _crypto_market(strike_type="greater", floor=71000.0)
    below = _crypto_market(strike_type="less", floor=None, cap=71000.0)
    p_above_on = _signal("on").generate(above).probability_yes
    p_below_on = _signal("on").generate(below).probability_yes
    assert p_above_on > 0.5 > p_below_on


def test_no_macro_data_abstains():
    # Non-destructive: no macro feed -> no signal.
    assert _signal("none").generate(_crypto_market()) is None


def test_signal_is_challenger_only_and_bounded():
    sig = _signal("on").generate(_crypto_market())
    assert sig.features["challenger_only"] is True
    assert 0.005 <= sig.probability_yes <= 0.995
    assert 0.20 <= sig.uncertainty <= 0.45
    assert sig.source == "crypto_macro_regime"


def test_abstains_when_crypto_state_missing_spot():
    sig = CryptoMacroRegimeSignal(
        fetch_state=lambda a: {"dvol": 60.0},  # no spot
        fetch_macro=lambda: {"sp500": 0.03, "dxy": -0.02},
        hours_to_close=lambda m: 12.0,
    )
    assert sig.generate(_crypto_market()) is None


def test_abstains_on_just_closed_market_no_throw():
    # A market whose close_time has passed (negative hours) must abstain, not
    # raise on sqrt(negative) -- the fail-closed contract.
    sig = CryptoMacroRegimeSignal(
        fetch_state=_state, fetch_macro=lambda: {"sp500": 0.03, "dxy": -0.02},
        hours_to_close=lambda m: -3.0,
    )
    assert sig.generate(_crypto_market()) is None


def test_abstains_on_non_numeric_dvol_no_throw():
    # A malformed vol field must abstain, not throw float("N/A").
    sig = CryptoMacroRegimeSignal(
        fetch_state=lambda a: {"spot": 71000.0, "dvol": "N/A"},
        fetch_macro=lambda: {"sp500": 0.03, "dxy": -0.02},
        hours_to_close=lambda m: 12.0,
    )
    assert sig.generate(_crypto_market()) is None


def test_short_horizon_drift_follows_sqrt_hours_law():
    # The at-the-money shift (in horizon-sigma units) grows as sqrt(hours), so a
    # 24h contract shifts ~sqrt(24/0.25)=9.8x as far off center as a 15-min one.
    # Assert the actual scaling law, not merely the direction.
    import math

    macro = {"sp500": 0.03, "dxy": -0.02, "vix": -0.15}
    market = _crypto_market()
    long = CryptoMacroRegimeSignal(
        fetch_state=_state, fetch_macro=lambda: macro, hours_to_close=lambda m: 24.0,
    ).generate(market)
    short = CryptoMacroRegimeSignal(
        fetch_state=_state, fetch_macro=lambda: macro, hours_to_close=lambda m: 0.25,
    ).generate(market)
    shift_long = long.features["shift_in_horizon_sigma"]
    shift_short = short.features["shift_in_horizon_sigma"]
    assert shift_short > 0 and shift_long > 0
    ratio = shift_long / shift_short
    assert abs(ratio - math.sqrt(24.0 / 0.25)) < 0.2  # ~9.8, the sqrt(hours) law
    assert abs(long.probability_yes - 0.5) > abs(short.probability_yes - 0.5)


def test_promotion_eligible_stamped_for_registered_sol_15m_scope_only():
    # Forward-registered candidate scope: crypto_macro_regime|sol|15m_direction|15m.
    from autonomy.signals.crypto_macro import PROMOTION_ELIGIBLE_SCOPE

    assert PROMOTION_ELIGIBLE_SCOPE == "crypto_macro_regime|sol|15m_direction|15m"
    sig = CryptoMacroRegimeSignal(
        fetch_state=lambda _asset: {"spot": 150.0, "dvol": 60.0},
        fetch_macro=lambda: {"sp500": 0.03, "dxy": -0.02},
        hours_to_close=lambda m: 0.25,
    )
    sol = sig.generate(
        _crypto_market(ticker="KXSOL15M-26JUL241200-00", floor=150.0)
    )
    assert sol is not None
    assert sol.features["promotion_eligible"] is True

    # Same source, different subject (btc): no opt-in stamp at all.
    btc = sig.generate(
        _crypto_market(ticker="KXBTC15M-26JUL241200-00", floor=150.0)
    )
    assert btc is not None
    assert "promotion_eligible" not in btc.features

    # Same subject, different contract family/horizon: no opt-in stamp.
    daily = CryptoMacroRegimeSignal(
        fetch_state=lambda _asset: {"spot": 150.0, "dvol": 60.0},
        fetch_macro=lambda: {"sp500": 0.03, "dxy": -0.02},
        hours_to_close=lambda m: 12.0,
    ).generate(_crypto_market(ticker="KXSOLD-26JUL0917-T150", floor=150.0))
    assert daily is not None
    assert "promotion_eligible" not in daily.features
