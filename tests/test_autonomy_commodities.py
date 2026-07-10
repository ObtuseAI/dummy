"""Tests for the commodities spot+vol signal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.commodities_spot import CommoditiesSpotVolSignal, _symbol_for


def _market(ticker="KXWTI-26JUL1014-T80.99", strike_type="greater", floor=80.99, cap=None):
    raw = {"strike_type": strike_type}
    if floor is not None:
        raw["floor_strike"] = floor
    if cap is not None:
        raw["cap_strike"] = cap
    return MarketView(
        ticker=ticker, title="WTI above 80.99", vertical=Vertical.COMMODITIES, status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
        yes_bid=20, yes_ask=30, no_bid=70, no_ask=80, volume=100, liquidity=100, raw=raw,
    )


def test_symbol_mapping():
    assert _symbol_for("KXWTI-26JUL1014-T80.99") == "CL=F"
    assert _symbol_for("KXNATGAS-26JUL10-T3") == "NG=F"
    assert _symbol_for("KXGOLD-26JUL10-T4000") == "GC=F"
    assert _symbol_for("KXHIGHNY-26JUL10-T85") is None


def test_greater_strike_below_spot_high_prob():
    # Spot 90 well above the 80.99 floor -> "above 80.99" very likely.
    sig = CommoditiesSpotVolSignal(fetch_spot_and_vol=lambda s: (90.0, 0.35))
    result = sig.generate(_market(floor=80.99))
    assert result is not None
    assert result.probability_yes > 0.8
    assert result.source == "commodities_spot_vol"
    assert result.uncertainty >= 0.10


def test_greater_strike_above_spot_low_prob():
    sig = CommoditiesSpotVolSignal(fetch_spot_and_vol=lambda s: (70.0, 0.35))
    result = sig.generate(_market(floor=80.99))
    assert result.probability_yes < 0.2


def test_less_strike_type():
    sig = CommoditiesSpotVolSignal(fetch_spot_and_vol=lambda s: (70.0, 0.35))
    result = sig.generate(_market(ticker="KXWTI-26JUL1014-T80", strike_type="less", floor=None, cap=80.0))
    assert result.probability_yes > 0.8  # spot 70 < 80 -> "below 80" likely


def test_fail_closed_on_feed_error():
    def boom(s):
        raise RuntimeError("yahoo down")

    sig = CommoditiesSpotVolSignal(fetch_spot_and_vol=boom)
    assert sig.generate(_market()) is None


def test_not_applicable_to_non_commodity():
    sig = CommoditiesSpotVolSignal(fetch_spot_and_vol=lambda s: (90.0, 0.35))
    weather = _market(ticker="KXHIGHNY-26JUL10-T85")
    object.__setattr__(weather, "vertical", Vertical.WEATHER)
    assert sig.applicable(weather) is False
