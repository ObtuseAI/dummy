"""On-chain liquidity challenger: stablecoin supply momentum -> crypto drift."""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_onchain import (
    CryptoOnchainLiquiditySignal,
    onchain_liquidity_score,
    stablecoin_supply_series,
)


def test_parse_defillama_chart_series():
    raw = [
        {"totalCirculatingUSD": {"peggedUSD": 300e9}},
        {"totalCirculatingUSD": {"peggedUSD": 305e9}},
        {"totalCirculatingUSD": {"peggedUSD": 0}},        # dropped (non-positive)
        {"totalCirculatingUSD": "not a dict"},             # dropped
    ]
    assert stablecoin_supply_series(raw) == [300e9, 305e9]


def test_score_positive_when_supply_expands():
    # Steadily rising supply -> positive (risk-on) score.
    series = [300e9 * (1.001 ** i) for i in range(40)]
    score, coverage, comps = onchain_liquidity_score(series)
    assert score > 0 and coverage == 1.0
    assert comps["supply_7d"] > 0 and comps["supply_30d"] > 0
    # Contracting supply -> negative.
    down = list(reversed(series))
    dscore, _, _ = onchain_liquidity_score(down)
    assert dscore < 0


def test_score_abstains_without_history():
    score, coverage, _ = onchain_liquidity_score([300e9, 301e9])
    assert coverage == 0.0 and score == 0.0


def _market(ticker="KXBTCD-26JAN01-B60000"):
    return MarketView(
        ticker=ticker, title="", vertical=Vertical.CRYPTO, status="open",
        close_time="2026-01-02T00:00:00+00:00",
        yes_bid=48, yes_ask=52, no_bid=48, no_ask=52, volume=100, liquidity=500,
        raw={"strike_type": "greater", "floor_strike": 60000},
    )


def test_signal_abstains_without_supply_feed():
    sig = CryptoOnchainLiquiditySignal(
        fetch_state=lambda a: {"spot": 62000.0, "dvol": 55.0},
        fetch_supply=lambda: [],
        hours_to_close=lambda m: 12.0,
    )
    assert sig.generate(_market()) is None


def test_signal_prices_with_expanding_supply():
    series = [300e9 * (1.002 ** i) for i in range(40)]
    sig = CryptoOnchainLiquiditySignal(
        fetch_state=lambda a: {"spot": 62000.0, "dvol": 55.0},
        fetch_supply=lambda: series,
        hours_to_close=lambda m: 24.0,
    )
    signal = sig.generate(_market())
    assert signal is not None
    assert signal.source == "crypto_onchain_liquidity"
    assert signal.features["onchain_liquidity_score"] > 0
    assert signal.features["expected_log_return"] > 0    # risk-on lifts BTC-up
    assert signal.features["challenger_only"] is True


def test_signal_abstains_on_bad_state():
    series = [300e9 * (1.002 ** i) for i in range(40)]
    sig = CryptoOnchainLiquiditySignal(
        fetch_state=lambda a: {"spot": 0.0},   # bad spot
        fetch_supply=lambda: series,
        hours_to_close=lambda m: 24.0,
    )
    assert sig.generate(_market()) is None
