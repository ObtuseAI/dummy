"""WS-17 BTC-to-alt lead-lag challenger (spot only, no perpetuals)."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_flows import (
    LEADLAG_MAX_SHIFT_SIGMA,
    CryptoBtcLeadlagSignal,
    leadlag_residual,
    move_in_sigma,
)

NOW = datetime(2026, 7, 12, 17, 0, tzinfo=timezone.utc)


def _market(ticker: str, hours: float = 1.0, **raw) -> MarketView:
    return MarketView(
        ticker=ticker, title="alt above?", vertical=Vertical.CRYPTO, status="open",
        close_time=(NOW + timedelta(hours=hours)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56, volume=100, liquidity=1_000, raw=raw,
    )


def _state(spot, minute_move_frac=0.0):
    # 200 hourly closes with a per-asset vol that is the SAME FRACTION of spot
    # across assets (so BTC and an alt share an annual vol and a given % move
    # equals the same number of sigmas), plus 30 minute closes whose last bar
    # jumps by minute_move_frac vs 15 minutes ago.
    hourly = [spot * (1.0 + 0.003 * (1 if i % 2 else -1)) for i in range(200)]
    hourly[-1] = spot
    minute = [spot] * 30
    minute[-1] = spot * (1.0 + minute_move_frac)
    return {"spot": spot, "hourly_closes": hourly,
            "minute_closes": minute, "minute_volumes": [5.0] * 30}


# -- pure functions ------------------------------------------------------------

def test_move_in_sigma_normalizes_by_own_vol():
    closes = [100.0] * 30
    closes[-1] = 101.0  # +1% over the window
    m = move_in_sigma(closes, 15, annual_vol=0.5)
    expected = math.log(1.01) / (0.5 * math.sqrt(15 / (60 * 24 * 365)))
    assert m == pytest.approx(expected)
    # Thin series or degenerate vol -> None.
    assert move_in_sigma([100.0] * 5, 15, 0.5) is None
    assert move_in_sigma(closes, 15, 0.0) is None


def test_leadlag_residual_floors_at_catch_up():
    # BTC +2 sigma, beta 0.7 -> target 1.4; alt only +0.5 -> 0.9 still owed.
    assert leadlag_residual(2.0, 0.5, 0.7) == pytest.approx(1.4 - 0.5)
    # Alt already caught up (>= target, same direction) -> floored to 0.
    assert leadlag_residual(2.0, 1.4, 0.7) == 0.0
    assert leadlag_residual(2.0, 3.0, 0.7) == 0.0
    # Alt diverged the wrong way -> even more catch-up owed (same sign as BTC).
    assert leadlag_residual(2.0, -1.0, 0.7) == pytest.approx(1.4 + 1.0)
    # Symmetric for a BTC down move.
    assert leadlag_residual(-2.0, -0.5, 0.7) == pytest.approx(-1.4 + 0.5)
    assert leadlag_residual(-2.0, -1.4, 0.7) == 0.0


# -- signal --------------------------------------------------------------------

def _signal(states: dict[str, dict]):
    return CryptoBtcLeadlagSignal(
        fetch_state=lambda asset: states[asset], hours_to_close=lambda _m: 1.0)


def test_leadlag_drifts_alt_up_when_btc_moved_and_alt_lagged():
    states = {
        "BTC": _state(64_000.0, minute_move_frac=0.02),  # BTC +2% recently
        "ETH": _state(3_500.0, minute_move_frac=0.0),    # ETH flat -> lagging
    }
    signal = _signal(states).generate(_market(
        "KXETHD-26JUL1318-T3500", hours=1.0, strike_type="greater", floor_strike=3_500.0))
    assert signal is not None
    assert signal.features["challenger_only"] is True
    assert signal.features["leadlag_residual_sigma"] > 0
    assert abs(signal.features["shift_in_horizon_sigma"]) <= LEADLAG_MAX_SHIFT_SIGMA + 1e-9
    # Lagging alt is expected to catch up -> P(above) above the driftless view.
    p_no_drift = 0.5  # spot == strike, no drift -> 0.5
    assert signal.probability_yes > p_no_drift


def test_leadlag_abstains_when_alt_already_tracked_btc():
    states = {
        "BTC": _state(64_000.0, minute_move_frac=0.02),
        "ETH": _state(3_500.0, minute_move_frac=0.02),  # ETH already moved with BTC
    }
    signal = _signal(states).generate(_market(
        "KXETHD-26JUL1318-T3500", strike_type="greater", floor_strike=3_500.0))
    assert signal is None  # residual floored -> no opinion


def test_leadlag_only_btc_alts_and_short_horizons():
    states = {"BTC": _state(64_000.0, 0.02), "ETH": _state(3_500.0, 0.0),
              "SOL": _state(160.0, 0.0)}
    sig = _signal(states)
    # BTC itself is not an alt -> not applicable.
    assert sig.applicable(_market("KXBTCD-26JUL1318-T64000")) is False
    assert sig.applicable(_market("KXETHD-26JUL1318-T3500")) is True
    # Daily horizon (26h to close) -> lead-lag is a minutes effect, abstain.
    daily_sig = CryptoBtcLeadlagSignal(
        fetch_state=lambda asset: states[asset], hours_to_close=lambda _m: 26.0)
    daily = daily_sig.generate(_market(
        "KXETHD-26JUL1318-T3500", strike_type="greater", floor_strike=3_500.0))
    assert daily is None


def test_leadlag_fails_closed_on_missing_or_thin_data():
    # Missing BTC state -> abstain.
    only_eth = CryptoBtcLeadlagSignal(
        fetch_state=lambda a: {"ETH": _state(3_500.0, 0.0)}.get(a) or (_ for _ in ()).throw(KeyError(a)),
        hours_to_close=lambda _m: 1.0)
    assert only_eth.generate(_market(
        "KXETHD-26JUL1318-T3500", strike_type="greater", floor_strike=3_500.0)) is None
    # Thin minute series -> abstain.
    thin = {"BTC": {"spot": 64_000.0, "hourly_closes": _state(64_000.0)["hourly_closes"],
                    "minute_closes": [64_000.0] * 5},
            "ETH": _state(3_500.0, 0.0)}
    assert _signal(thin).generate(_market(
        "KXETHD-26JUL1318-T3500", strike_type="greater", floor_strike=3_500.0)) is None


def test_no_perpetual_data_touched():
    # Guard the operator directive: no perpetual/derivative API identifiers.
    # Match exact API tokens (not the docstring's plain-English negation).
    import autonomy.signals.crypto_flows as flows

    source = open(flows.__file__, encoding="utf-8").read()
    for banned in ("funding_8h", "instrument_name", "PERPETUAL", "mark_price",
                   "index_price", "get_volatility"):
        assert banned not in source, f"lead-lag must not reference {banned!r}"
