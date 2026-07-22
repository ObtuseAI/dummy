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


def test_commodity_signal_is_retired_data_only():
    sig = CommoditiesSpotVolSignal(fetch_spot_and_vol=lambda s: (90.0, 0.35))
    assert sig.data_only is True
    assert sig.prediction_authority is False
    assert sig.applicable(_market()) is False
    assert sig.generate(_market()) is None


def test_not_applicable_to_non_commodity():
    sig = CommoditiesSpotVolSignal(fetch_spot_and_vol=lambda s: (90.0, 0.35))
    weather = _market(ticker="KXHIGHNY-26JUL10-T85")
    object.__setattr__(weather, "vertical", Vertical.WEATHER)
    assert sig.applicable(weather) is False
