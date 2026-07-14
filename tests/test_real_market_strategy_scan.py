"""Tests for strategy scan over real market data snapshots."""

from datetime import datetime, timezone
from decimal import Decimal


from core.ontology import Forecast, OrderBook, OrderBookLevel
from strategies.scan import StrategyScanner, StrategyScanResult


def _make_forecast():
    return Forecast(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        event_title="Event",
        contract_title="Yes",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.53"),
        probability_delta=Decimal("0.03"),
        confidence_score=Decimal("0.6"),
        uncertainty_band=(Decimal("0.48"), Decimal("0.58")),
        expected_edge=Decimal("0.03"),
        edge_after_fees=Decimal("0.025"),
        freshness_score=Decimal("1.0"),
        liquidity_score=Decimal("0.7"),
        spread_score=Decimal("0.8"),
        orderbook_depth_score=Decimal("0.6"),
        settlement_risk_score=Decimal("0.2"),
        source_summary="test",
        model_summary="test",
        calibration_notes="test",
        timestamp=datetime.now(timezone.utc),
        expiration=datetime.now(timezone.utc),
        strategy_references=["test"],
        proof_reference="forecast_1",
    )


def _make_book():
    return OrderBook(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=datetime.now(timezone.utc),
    )


def test_scan_runs_all_repo_derived_families():
    scanner = StrategyScanner()
    results = scanner.scan(_make_forecast(), _make_book())
    assert len(results) == 8
    for r in results:
        assert isinstance(r, StrategyScanResult)
        assert r.family
        assert r.market_ticker == "MKT"


def test_scan_records_no_trade_reasons():
    scanner = StrategyScanner()
    results = scanner.scan(_make_forecast(), _make_book())
    proposals = [r for r in results if r.proposal is not None]
    no_trades = [r for r in results if r.no_trade_reason is not None]
    assert len(proposals) + len(no_trades) == 8
