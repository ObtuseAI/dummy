"""Crypto equities/ETF flow challenger invariants."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_equities import (
    EQUITY_DIVERGENCE_PENALTY,
    EQUITY_FLOW_AMPLIFIER_CAP,
    EQUITY_MAX_SHIFT_SIGMA,
    CryptoEquitiesSignal,
    _volume_surge,
    equity_flow_score,
)

NOW = datetime(2026, 7, 12, 17, 0, tzinfo=timezone.utc)


def _market(ticker: str = "KXBTCD-26JUL1317-T70000", hours: float = 24.0, **raw) -> MarketView:
    return MarketView(
        ticker=ticker, title="crypto?", vertical=Vertical.CRYPTO, status="open",
        close_time=(NOW + timedelta(hours=hours)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=100, liquidity=1_000, raw=raw,
    )


def _hub_state(momentum_up: bool = True) -> dict:
    # 30 hourly closes trending up or down; spot 71000; dvol present.
    step = 40.0 if momentum_up else -40.0
    hourly = [71_000.0 - step * (30 - index) for index in range(30)]
    return {
        "spot": 71_000.0,
        "dvol": 50.0,
        "hourly_closes": hourly,
        "minute_closes": [hourly[-1]] * 60,
        "minute_volumes": [5.0] * 60,
    }


def _equity_state(change: float = 0.04, surge: float | None = None) -> dict:
    changes = {key: change for key in ("ibit", "fbtc", "etha", "mstr", "coin", "mara", "riot")}
    return {
        "changes": changes,
        "etf_volume_surges": {"ibit": surge} if surge is not None else {},
    }


def _signal(equity_state: dict, hub_state: dict) -> CryptoEquitiesSignal:
    return CryptoEquitiesSignal(
        fetch_state=lambda _asset: hub_state,
        fetch_equities=lambda: equity_state,
        hours_to_close=lambda _m: 24.0,
    )


# -- scoring -------------------------------------------------------------------

def test_equity_flow_score_is_bounded_asset_weighted_and_coverage_honest():
    changes = {"ibit": 0.06, "etha": 0.06, "mstr": 0.10}
    btc_score, btc_cov, btc_parts = equity_flow_score(changes, "BTC")
    eth_score, eth_cov, _ = equity_flow_score(changes, "ETH")
    assert 0 < btc_score <= 1.0 and 0 < eth_score <= 1.0
    # The ETH ETF matters more for ETH than for BTC.
    assert eth_cov > 0 and btc_cov > 0
    assert btc_parts["etha"] < btc_score  # down-weighted contributor
    empty_score, empty_cov, _ = equity_flow_score({}, "BTC")
    assert empty_score == 0.0 and empty_cov == 0.0
    # Coverage never exceeds 1 even with every factor present.
    _full, full_cov, _ = equity_flow_score(
        {k: 0.02 for k in ("ibit", "fbtc", "etha", "mstr", "coin", "mara", "riot")}, "BTC")
    assert full_cov == pytest.approx(1.0)


def test_volume_surge_needs_history_and_reads_flow():
    assert _volume_surge([1000.0] * 10) is None
    flat = [1000.0] * 20
    assert _volume_surge(flat) == pytest.approx(1.0)
    surging = [1000.0] * 15 + [3000.0] * 5
    assert _volume_surge(surging) == pytest.approx(3.0)


# -- signal doctrine -------------------------------------------------------------

def test_signal_emits_bounded_positive_drift_on_risk_on_complex():
    signal = _signal(_equity_state(0.05), _hub_state()).generate(
        _market(strike_type="greater", floor_strike=70_000.0))
    assert signal is not None
    assert signal.features["challenger_only"] is True
    assert abs(signal.features["shift_in_horizon_sigma"]) <= EQUITY_MAX_SHIFT_SIGMA + 1e-9
    sigma = 0.50 * math.sqrt(24.0 / (24 * 365))
    p_no_drift = 0.5 * (1.0 + math.erf(math.log(71_000.0 / 70_000.0) / sigma / math.sqrt(2)))
    assert signal.probability_yes > p_no_drift  # risk-on shifts P(above) up


def test_flow_amplifier_engages_on_etf_volume_surge_and_is_capped():
    # Small score keeps raw drift BELOW the sigma cap so the amplifier's
    # effect on the drift itself is strictly observable (not cap-pinned).
    calm = _signal(_equity_state(0.008), _hub_state()).generate(_market())
    surging = _signal(_equity_state(0.008, surge=3.0), _hub_state()).generate(_market())
    assert calm is not None and surging is not None
    assert surging.features["flow_amplifier"] > 1.0
    assert surging.features["flow_amplifier"] <= EQUITY_FLOW_AMPLIFIER_CAP
    assert abs(surging.features["expected_log_return"]) > abs(calm.features["expected_log_return"])
    # And at saturation the sigma cap still binds both.
    pinned = _signal(_equity_state(0.05, surge=3.0), _hub_state()).generate(_market())
    assert abs(pinned.features["shift_in_horizon_sigma"]) <= EQUITY_MAX_SHIFT_SIGMA + 1e-9


def test_divergence_from_spot_tape_widens_uncertainty_only():
    aligned = _signal(_equity_state(0.05), _hub_state(momentum_up=True)).generate(_market())
    diverging = _signal(_equity_state(0.05), _hub_state(momentum_up=False)).generate(_market())
    assert aligned is not None and diverging is not None
    assert diverging.features["spot_equity_divergence"] is True
    assert aligned.features["spot_equity_divergence"] is False
    assert diverging.uncertainty >= aligned.uncertainty + EQUITY_DIVERGENCE_PENALTY - 1e-9
    # The mean shift itself is unchanged by divergence -- only confidence drops.
    assert diverging.features["expected_log_return"] == pytest.approx(
        aligned.features["expected_log_return"])


def test_abstention_matrix_and_remaining_strike_shapes():
    equities = _equity_state(0.05)
    market = _market(strike_type="greater", floor_strike=70_000.0)
    # Missing spot / zero spot.
    for bad in ({**_hub_state(), "spot": None}, {**_hub_state(), "spot": 0.0}):
        assert _signal(equities, bad).generate(market) is None
    # Non-numeric dvol and no realized-vol fallback (thin series).
    thin = {**_hub_state(), "dvol": "garbage", "hourly_closes": [], "minute_closes": []}
    assert _signal(equities, thin).generate(market) is None
    # Just-closed market: hours <= 0 abstains, never sqrt(negative).
    closed = CryptoEquitiesSignal(
        fetch_state=lambda _asset: _hub_state(),
        fetch_equities=lambda: equities,
        hours_to_close=lambda _m: 0.0,
    )
    assert closed.generate(market) is None
    # 'less' and 'between' strike shapes mirror the champion's handling.
    base = _signal(equities, _hub_state())
    p_greater = base.generate(_market(strike_type="greater", floor_strike=70_000.0))
    p_less = base.generate(_market(strike_type="less", cap_strike=70_000.0))
    p_between = base.generate(_market(
        strike_type="between", floor_strike=70_000.0, cap_strike=72_000.0))
    assert p_greater is not None and p_less is not None and p_between is not None
    assert p_less.probability_yes == pytest.approx(
        1.0 - p_greater.probability_yes, abs=1e-9)
    assert 0.0 < p_between.probability_yes < p_greater.probability_yes


def test_fails_closed_without_equity_data_or_hub_state():
    market = _market(strike_type="greater", floor_strike=70_000.0)
    no_equities = CryptoEquitiesSignal(
        fetch_state=lambda _asset: _hub_state(),
        fetch_equities=lambda: {"changes": {}},
        hours_to_close=lambda _m: 24.0,
    )
    assert no_equities.generate(market) is None

    def _raising():
        raise ValueError("yahoo down")

    fetch_raises = CryptoEquitiesSignal(
        fetch_state=lambda _asset: _hub_state(),
        fetch_equities=_raising,
        hours_to_close=lambda _m: 24.0,
    )
    assert fetch_raises.generate(market) is None

    def _hub_raises(_asset):
        raise ValueError("hub down")

    no_hub = CryptoEquitiesSignal(
        fetch_state=_hub_raises,
        fetch_equities=lambda: _equity_state(0.05),
        hours_to_close=lambda _m: 24.0,
    )
    assert no_hub.generate(market) is None
    # Non-crypto market: not applicable.
    mlb = MarketView(
        ticker="KXMLBGAME-26JUL122005HOUTEX-HOU", title="mlb", vertical=Vertical.SPORTS,
        status="open", close_time=NOW.isoformat(), yes_bid=44, yes_ask=46,
        no_bid=54, no_ask=56, volume=1, liquidity=1, raw={},
    )
    assert not no_equities.applicable(mlb)


def test_subdaily_equity_flow_abstains_before_fetching_slow_sources():
    calls = {"equities": 0, "hub": 0}

    def equities():
        calls["equities"] += 1
        return _equity_state(0.05)

    def hub(_asset):
        calls["hub"] += 1
        return _hub_state()

    signal = CryptoEquitiesSignal(
        fetch_state=hub,
        fetch_equities=equities,
        hours_to_close=lambda _market: 0.25,
    )
    assert signal.generate(
        _market(ticker="KXSOL15M-26JUL241200-00")
    ) is None
    assert calls == {"equities": 0, "hub": 0}


def test_promotion_eligible_stamped_for_registered_sol_daily_scope_only():
    from autonomy.signals.crypto_equities import PROMOTION_ELIGIBLE_SCOPE

    assert PROMOTION_ELIGIBLE_SCOPE == "crypto_equities_flow|sol|ladder|daily+"
    signal = _signal(_equity_state(0.05), _hub_state())
    sol = signal.generate(
        _market(ticker="KXSOLD-26JUL0917-T71000", strike_type="greater",
                floor_strike=71_000.0)
    )
    assert sol is not None
    assert sol.features["promotion_eligible"] is True

    btc = signal.generate(
        _market(ticker="KXBTCD-26JUL0917-T71000", strike_type="greater",
                floor_strike=71_000.0)
    )
    assert btc is not None
    assert "promotion_eligible" not in btc.features

    short = signal.generate(
        _market(ticker="KXSOL15M-26JUL241200-00", strike_type="greater",
                floor_strike=71_000.0)
    )
    assert short is None
