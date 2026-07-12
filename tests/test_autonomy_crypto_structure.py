"""Multi-timeframe structure engine + swing challenger invariants."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autonomy.crypto_structure import (
    aggregate_closes,
    cluster_levels,
    mtf_alignment,
    structure_state,
    swing_points,
    swing_setup,
    trend_channel,
)
from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_structure import (
    MIN_SETUP_SCORE,
    CryptoStructureSignal,
)

NOW = datetime(2026, 7, 12, 17, 0, tzinfo=timezone.utc)


def _market(hours: float = 24.0, **raw) -> MarketView:
    return MarketView(
        ticker="KXBTCD-26JUL1317-T70000", title="BTC above 70000?",
        vertical=Vertical.CRYPTO, status="open",
        close_time=(NOW + timedelta(hours=hours)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=100, liquidity=1_000, raw=raw,
    )


def _bouncing_series(floor: float, ceiling: float, cycles: int, period: int = 12) -> list[float]:
    """Price oscillating between a floor and ceiling: clean S/R structure."""
    closes: list[float] = []
    half = period // 2
    step = (ceiling - floor) / half
    for _cycle in range(cycles):
        closes.extend(floor + step * index for index in range(half))
        closes.extend(ceiling - step * index for index in range(half))
    closes.append(floor)  # finish sitting on the floor
    return closes


# -- pure structure functions ---------------------------------------------------

def test_swing_points_confirm_extrema_and_thin_series_yield_nothing():
    series = _bouncing_series(70_000.0, 71_200.0, cycles=4)
    swings = swing_points(series)
    kinds = {kind for _idx, _price, kind in swings}
    assert kinds == {"high", "low"}
    highs = [price for _idx, price, kind in swings if kind == "high"]
    lows = [price for _idx, price, kind in swings if kind == "low"]
    assert all(price == pytest.approx(71_200.0, rel=1e-6) for price in highs)
    assert all(price == pytest.approx(70_000.0, rel=1e-6) for price in lows)
    assert swing_points([70_000.0] * 5) == []


def test_cluster_levels_merges_touches_and_ranks_by_recency_weighted_strength():
    series = _bouncing_series(70_000.0, 71_200.0, cycles=4)
    levels = cluster_levels(swing_points(series), len(series))
    assert len(levels) == 2
    floor_level = next(level for level in levels if level.price < 70_500)
    ceiling_level = next(level for level in levels if level.price > 70_500)
    assert floor_level.kind == "support" and floor_level.touches >= 3
    assert ceiling_level.kind == "resistance" and ceiling_level.touches >= 3
    assert floor_level.strength > 0 and ceiling_level.strength > 0


def test_trend_channel_reads_slope_direction_and_band_position():
    up = [70_000.0 + 25.0 * index for index in range(60)]
    channel = trend_channel(up)
    assert channel is not None and channel.slope_bps_per_bar > 0
    assert channel.r_squared > 0.99
    down = [71_500.0 - 25.0 * index for index in range(60)]
    assert trend_channel(down).slope_bps_per_bar < 0
    assert trend_channel([70_000.0] * 10) is None  # thin -> no channel


def test_structure_state_builds_timeframes_and_alignment_votes():
    hourly = [70_000.0 + 8.0 * index for index in range(300)]
    state = {
        "spot": hourly[-1],
        "minute_closes": [hourly[-1]] * 30,
        "hourly_closes": hourly,
        "daily_closes": [69_000.0 + 120.0 * index for index in range(30)],
    }
    structures = structure_state(state)
    assert {"1m", "1h", "4h", "1d"} <= set(structures)
    assert mtf_alignment(structures) > 0.5  # all frames trend up
    assert aggregate_closes(hourly, 4)[-1] == hourly[-1]
    # Without real daily candles the hourly fallback (300h -> 12 bars) is
    # too thin for structure, so the 1d frame honestly drops out rather
    # than opining on a dozen points.
    del state["daily_closes"]
    fallback = structure_state(state)
    assert "1d" not in fallback and {"1m", "1h", "4h"} <= set(fallback)


def test_swing_setup_goes_long_at_support_with_confirmation_and_vetoes_on_book():
    series = _bouncing_series(70_000.0, 71_200.0, cycles=6)
    structures = structure_state({
        "spot": 70_010.0,  # sitting on the floor
        "minute_closes": series[-40:],
        "hourly_closes": series,
        "daily_closes": [],
    })
    confirmed = swing_setup(structures, {
        "top_book_imbalance": 0.4, "microprice_basis_bps": 3.0,
        "volume_surge_15m": 2.0,
    })
    assert confirmed.score >= MIN_SETUP_SCORE
    assert any("support" in reason for reason in confirmed.reasons)
    # A heavily offered book vetoes the long even at structure.
    vetoed = swing_setup(structures, {"top_book_imbalance": -0.6})
    assert vetoed.score == 0.0
    assert any("order book contradicts" in reason for reason in vetoed.reasons)
    # Structure alone -- zero confirming technicals -- is NOT a setup
    # (operator directive: swings need the rest of the technicals).
    unconfirmed = swing_setup(structures, {})
    assert unconfirmed.score == 0.0
    assert any("no confirming technicals" in r for r in unconfirmed.reasons)
    # Non-directional volume alone cannot green-light a direction either.
    volume_only = swing_setup(structures, {"volume_surge_15m": 3.0})
    assert volume_only.score == 0.0
    assert any("no confirming technicals" in r for r in volume_only.reasons)
    # Mid-range price: no actionable level, no setup.
    mid = structure_state({
        "spot": 70_600.0, "minute_closes": series[-40:],
        "hourly_closes": series, "daily_closes": [],
    })
    assert swing_setup(mid, {}).score == 0.0


# -- challenger signal ------------------------------------------------------------

def _setup_state(spot: float) -> dict:
    series = _bouncing_series(70_000.0, 71_200.0, cycles=6)
    return {
        "spot": spot,
        "minute_closes": series[-60:],
        "minute_volumes": [5.0] * 60,
        "hourly_closes": series,
        "daily_closes": [],
        "book_imbalance": 0.5,
        "microprice_basis_bps": 4.0,
        "dvol": 50.0,
        "hourly_source": "coinbase",
    }


def test_structure_signal_opines_only_at_setups_and_stays_challenger_only():
    at_support = CryptoStructureSignal(
        fetch_state=lambda _asset: _setup_state(70_010.0),
        hours_to_close=lambda _m: 24.0,
    )
    market = _market(strike_type="greater", floor_strike=70_000.0)
    signal = at_support.generate(market)
    assert signal is not None
    assert signal.features["challenger_only"] is True
    assert signal.features["setup_score"] >= MIN_SETUP_SCORE
    assert signal.features["shift_in_horizon_sigma"] <= 0.45 + 1e-9
    assert 0.005 <= signal.probability_yes <= 0.995
    assert signal.features["structure"]["1h"]["support"] is not None

    # Long setup at support must shift P(above) UP versus the driftless view.
    import math

    from autonomy.signals.crypto_spot import _normal_cdf

    sigma = 0.50 * math.sqrt(24.0 / (24 * 365))
    p_no_drift = _normal_cdf(math.log(70_010.0 / 70_000.0) / sigma)
    assert signal.probability_yes > p_no_drift

    # Mid-range spot: no setup, no signal -- the scalpel abstains.
    mid = CryptoStructureSignal(
        fetch_state=lambda _asset: _setup_state(70_600.0),
        hours_to_close=lambda _m: 24.0,
    )
    assert mid.generate(market) is None


def test_structure_signal_integration_veto_and_confirmation_gate():
    """The veto and the confirmation gate must work through generate() --
    i.e. via the REAL _indicator_features key names, not hand-built dicts."""
    market = _market(strike_type="greater", floor_strike=70_000.0)

    # Hostile order book in the raw hub state (state key book_imbalance ->
    # feature top_book_imbalance): the long at support must be vetoed.
    hostile = CryptoStructureSignal(
        fetch_state=lambda _asset: {**_setup_state(70_010.0), "book_imbalance": -0.9},
        hours_to_close=lambda _m: 24.0,
    )
    assert hostile.generate(market) is None

    # Structure alone -- no confirming technical anywhere -- must abstain
    # (operator directive: swings need the rest of the technicals).
    bare = CryptoStructureSignal(
        fetch_state=lambda _asset: {
            **_setup_state(70_010.0),
            "book_imbalance": None,
            "microprice_basis_bps": None,
        },
        hours_to_close=lambda _m: 24.0,
    )
    assert bare.generate(market) is None


def test_structure_signal_fails_closed_on_missing_state():
    def _raising(_asset):
        raise ValueError("hub down")

    signal = CryptoStructureSignal(fetch_state=_raising, hours_to_close=lambda _m: 24.0)
    assert signal.generate(_market(strike_type="greater", floor_strike=70_000.0)) is None
    thin = CryptoStructureSignal(
        fetch_state=lambda _asset: {"spot": 70_000.0, "hourly_closes": [], "minute_closes": []},
        hours_to_close=lambda _m: 24.0,
    )
    assert thin.generate(_market(strike_type="greater", floor_strike=70_000.0)) is None
