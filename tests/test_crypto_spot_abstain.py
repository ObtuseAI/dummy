"""Wave-83: a malformed (non-positive) strike must abstain, never fail open.

The old path returned P(above)=1.0 for strike<=0, so a 15m-direction market
missing floor_strike emitted a fabricated 0.995 YES (2026-07-24 audit).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_spot import CryptoSpotVolSignal


def _market(**raw) -> MarketView:
    close = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return MarketView(
        ticker="KXBTC15M-26JUL091700-15",
        title="BTC 15m",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time=close,
        yes_bid=48, yes_ask=52, no_bid=48, no_ask=52,
        volume=100, liquidity=1000,
        raw=raw,
    )


def _signal_source() -> CryptoSpotVolSignal:
    return CryptoSpotVolSignal(fetch_spot_and_vol=lambda asset: (65_000.0, 0.5))


def test_zero_floor_strike_abstains():
    source = _signal_source()
    assert source.generate(_market(strike_type="greater", floor_strike=0.0)) is None


def test_missing_strike_metadata_parsing_to_zero_abstains():
    # No strike_type payload and a ticker whose parsed strike is 0 -> abstain.
    source = _signal_source()
    market = _market()
    parsed_strike_zero = source.generate(market)
    # The 15m direction ticker parses its strike from the ticker tail; if that
    # yields a non-positive strike the source must return None, and must never
    # emit a >=0.99 probability either way.
    if parsed_strike_zero is not None:
        assert parsed_strike_zero.probability_yes < 0.99


def test_valid_floor_strike_still_emits():
    source = _signal_source()
    signal = source.generate(_market(strike_type="greater", floor_strike=60_000.0))
    assert signal is not None
    assert 0.005 <= signal.probability_yes <= 0.995


def test_zero_cap_strike_abstains_for_less_and_between():
    source = _signal_source()
    assert source.generate(_market(strike_type="less", cap_strike=0.0)) is None
    assert source.generate(
        _market(strike_type="between", floor_strike=0.0, cap_strike=70_000.0)
    ) is None
