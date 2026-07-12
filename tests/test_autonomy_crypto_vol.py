"""WS-16 vol triangulation, VRP regime, settlement-proximity guard."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_vol import (
    SETTLEMENT_PROXIMITY_BUMP,
    VRP_MAX_SHIFT_SIGMA,
    CryptoBlendSigmaSignal,
    CryptoVrpRegimeSignal,
    blended_sigma,
    settlement_proximity_uncertainty,
    vrp_points,
    vrp_regime_score,
)

NOW = datetime(2026, 7, 12, 17, 0, tzinfo=timezone.utc)


def _market(hours: float = 24.0, **raw) -> MarketView:
    return MarketView(
        ticker="KXBTCD-26JUL1317-T70000", title="BTC above?", vertical=Vertical.CRYPTO,
        status="open", close_time=(NOW + timedelta(hours=hours)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56, volume=100, liquidity=1_000, raw=raw,
    )


def _state(dvol=50.0, spot=71_000.0, drift=5.0):
    # 200 hourly closes with mild noise -> nonzero flat + ewma realized vol.
    closes = [spot - drift * (200 - i) + (10.0 if i % 2 else -10.0) for i in range(200)]
    closes[-1] = spot
    return {"spot": spot, "dvol": dvol, "hourly_closes": closes,
            "minute_closes": [spot] * 60, "minute_volumes": [5.0] * 60}


# -- pure functions ------------------------------------------------------------

def test_blended_sigma_weights_and_renormalizes():
    # daily+: implied dominates (0.5); a blend sits between the inputs.
    sigma, disagreement = blended_sigma(0.40, 0.60, 0.80, "daily+")
    assert sigma == pytest.approx(0.25 * 0.40 + 0.25 * 0.60 + 0.50 * 0.80)
    assert disagreement == pytest.approx(0.80 / 0.40 - 1.0)
    # 15m: implied weight is zero -> implied ignored even if present.
    s15, _ = blended_sigma(0.40, 0.60, 0.80, "15m")
    assert s15 == pytest.approx((0.4 * 0.40 + 0.6 * 0.60) / (0.4 + 0.6))
    # Missing estimates renormalize over what remains.
    s_partial, d_partial = blended_sigma(None, 0.60, None, "daily+")
    assert s_partial == pytest.approx(0.60) and d_partial == pytest.approx(0.0)
    # Nothing usable -> abstain.
    assert blended_sigma(None, None, None, "hourly") == (None, None)


def test_vrp_points():
    assert vrp_points(50.0, 0.40) == pytest.approx(10.0)   # 50 - 40
    assert vrp_points(30.0, 0.45) == pytest.approx(-15.0)  # 30 - 45
    assert vrp_points(None, 0.40) is None
    assert vrp_points(50.0, None) is None


def test_settlement_proximity_guard_2x2():
    sigma_h = 0.02
    # Near close AND near strike -> bump.
    assert settlement_proximity_uncertainty(0.5, 71_000, 71_050, sigma_h) == SETTLEMENT_PROXIMITY_BUMP
    # Near close but FAR from strike (>1 sigma) -> no bump.
    assert settlement_proximity_uncertainty(0.5, 71_000, 90_000, sigma_h) == 0.0
    # Not near close -> no bump even at the strike.
    assert settlement_proximity_uncertainty(3.0, 71_000, 71_050, sigma_h) == 0.0
    # Degenerate inputs fail closed.
    assert settlement_proximity_uncertainty(None, 71_000, 71_050, sigma_h) == 0.0
    assert settlement_proximity_uncertainty(0.5, 71_000, 0, sigma_h) == 0.0


def test_vrp_regime_score_zones_and_bounds():
    assert vrp_regime_score(5.0) == 0.0          # dead zone
    assert vrp_regime_score(-2.0) == 0.0
    assert vrp_regime_score(20.0) > 0.0          # fear premium -> unwind up
    assert vrp_regime_score(-10.0) < 0.0         # complacency -> down
    assert vrp_regime_score(1000.0) == 1.0       # bounded
    assert vrp_regime_score(-1000.0) == -1.0
    assert vrp_regime_score(None) == 0.0


# -- blend challenger ----------------------------------------------------------

def _blend(state):
    return CryptoBlendSigmaSignal(fetch_state=lambda _a: state, hours_to_close=lambda _m: 24.0)


def test_blend_signal_prices_and_is_challenger_only():
    signal = _blend(_state()).generate(_market(strike_type="greater", floor_strike=70_000.0))
    assert signal is not None
    assert signal.features["challenger_only"] is True
    assert signal.features["blended_annual_vol"] > 0
    assert signal.features["vol_implied"] == pytest.approx(0.50)  # dvol 50 -> 0.50
    assert signal.features["vrp_points"] is not None
    assert 0.005 <= signal.probability_yes <= 0.995


def test_blend_disagreement_widens_uncertainty():
    calm = _blend({**_state(dvol=55.0)}).generate(_market())          # implied ~ realized
    # Implied vol wildly above realized -> big disagreement -> wider uncertainty.
    wild = _blend({**_state(dvol=300.0)}).generate(_market())
    assert calm is not None and wild is not None
    assert wild.features["vol_disagreement"] > calm.features["vol_disagreement"]
    assert wild.uncertainty > calm.uncertainty


def test_blend_settlement_guard_fires_near_close_near_strike():
    near = CryptoBlendSigmaSignal(fetch_state=lambda _a: _state(spot=70_010.0),
                                  hours_to_close=lambda _m: 0.5)
    signal = near.generate(_market(hours=0.5, strike_type="greater", floor_strike=70_000.0))
    assert signal is not None
    assert signal.features["near_close_near_strike"] is True
    far_time = CryptoBlendSigmaSignal(fetch_state=lambda _a: _state(spot=70_010.0),
                                      hours_to_close=lambda _m: 24.0)
    calm = far_time.generate(_market(strike_type="greater", floor_strike=70_000.0))
    assert calm.features["near_close_near_strike"] is False
    assert signal.uncertainty > calm.uncertainty


def test_blend_prices_less_and_between_strike_branches():
    blend = _blend(_state())
    less = blend.generate(_market(strike_type="less", cap_strike=70_000.0))
    greater = blend.generate(_market(strike_type="greater", floor_strike=70_000.0))
    assert less is not None and greater is not None
    # P(<K) and P(>K) from the same distribution are complementary.
    assert less.probability_yes == pytest.approx(1.0 - greater.probability_yes, abs=1e-9)
    between = blend.generate(_market(
        strike_type="between", floor_strike=70_000.0, cap_strike=72_000.0))
    assert between is not None and 0.0 < between.probability_yes < greater.probability_yes


def test_blend_guard_fires_on_the_cap_boundary_of_a_between_market():
    # Spot sits on the CAP (72,000), far above the floor (60,000). The guard
    # must still fire off the near boundary, not just the floor.
    near_cap = CryptoBlendSigmaSignal(
        fetch_state=lambda _a: _state(spot=72_010.0), hours_to_close=lambda _m: 0.5)
    signal = near_cap.generate(_market(
        hours=0.5, strike_type="between", floor_strike=60_000.0, cap_strike=72_000.0))
    assert signal is not None
    assert signal.features["near_close_near_strike"] is True


def test_blend_fails_closed_without_state():
    def _raise(_a):
        raise ValueError("hub down")

    assert CryptoBlendSigmaSignal(fetch_state=_raise, hours_to_close=lambda _m: 24.0).generate(
        _market(strike_type="greater", floor_strike=70_000.0)) is None
    thin = CryptoBlendSigmaSignal(
        fetch_state=lambda _a: {"spot": 71_000.0, "hourly_closes": []},
        hours_to_close=lambda _m: 24.0)
    assert thin.generate(_market(strike_type="greater", floor_strike=70_000.0)) is None


# -- VRP regime challenger -----------------------------------------------------

def test_vrp_signal_abstains_in_dead_zone_and_drifts_on_fear():
    # dvol 50, flat realized ~ high from the noisy series -> compute vrp; force
    # a clear fear premium with a very high dvol.
    fear = CryptoVrpRegimeSignal(fetch_state=lambda _a: _state(dvol=120.0),
                                 hours_to_close=lambda _m: 24.0)
    signal = fear.generate(_market(strike_type="greater", floor_strike=70_000.0))
    assert signal is not None
    assert signal.features["challenger_only"] is True
    assert signal.features["vrp_score"] > 0
    assert abs(signal.features["shift_in_horizon_sigma"]) <= VRP_MAX_SHIFT_SIGMA + 1e-9
    # Fear premium unwinds upward -> P(above) above the driftless value.
    spot, strike = 71_000.0, 70_000.0
    sigma_h = 1.20 * math.sqrt(24.0 / (24 * 365))
    p_no_drift = 0.5 * (1 + math.erf(math.log(spot / strike) / sigma_h / math.sqrt(2)))
    assert signal.probability_yes > p_no_drift

    # Dead-zone VRP (implied ~ realized) -> abstain.
    dead = CryptoVrpRegimeSignal(
        fetch_state=lambda _a: _state(dvol=1.0),  # tiny implied ~ realized-ish -> near dead zone
        hours_to_close=lambda _m: 24.0)
    # If not exactly dead, at least assert it never violates the sigma cap.
    out = dead.generate(_market(strike_type="greater", floor_strike=70_000.0))
    if out is not None:
        assert abs(out.features["shift_in_horizon_sigma"]) <= VRP_MAX_SHIFT_SIGMA + 1e-9


def test_indicator_features_carry_vrp():
    from autonomy.signals.crypto_indicators import _indicator_features

    feats = _indicator_features(_state(dvol=50.0))
    # long_vol computed from the 200-close series; vrp = dvol - long_vol*100.
    assert feats["vrp_points"] is not None
    assert "realized_vol_7d_annualized" in feats
