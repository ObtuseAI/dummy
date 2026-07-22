"""Tests for strategy scan over real market data snapshots."""

from datetime import datetime, timezone
from decimal import Decimal


from core.ontology import Forecast, OrderBook, OrderBookLevel
from strategies.repo_derived import (
    CommoditiesEnergyStrategy,
    KalshiWeatherForecastStrategy,
    StockMacroMomentumStrategy,
)
from strategies.registry import (
    ACTIVE_REPO_DERIVED_FAMILY_COUNT,
    ACTIVE_REPO_DERIVED_FAMILY_NAMES,
)
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


def test_scan_runs_all_active_repo_derived_families():
    scanner = StrategyScanner()
    results = scanner.scan(_make_forecast(), _make_book())
    expected_families = (
        "sports_momentum",
        "crypto_event_market",
        "repo_derived_cross_market_arbitrage",
        "orderbook_spread_capture",
        "stale_quote_detection",
    )
    assert scanner.active_family_count == ACTIVE_REPO_DERIVED_FAMILY_COUNT == 5
    assert scanner.active_family_names == ACTIVE_REPO_DERIVED_FAMILY_NAMES == expected_families
    assert tuple(result.family for result in results) == scanner.active_family_names
    for r in results:
        assert isinstance(r, StrategyScanResult)
        assert r.family
        assert r.market_ticker == "MKT"


def test_scan_records_no_trade_reasons():
    scanner = StrategyScanner()
    results = scanner.scan(_make_forecast(), _make_book())
    proposals = [r for r in results if r.proposal is not None]
    no_trades = [r for r in results if r.no_trade_reason is not None]
    assert len(proposals) + len(no_trades) == scanner.active_family_count


def test_non_authoritative_families_cannot_be_injected_into_strategy_scan():
    retired = [
        KalshiWeatherForecastStrategy(),
        CommoditiesEnergyStrategy(),
        StockMacroMomentumStrategy(),
    ]
    scanner = StrategyScanner(strategies=retired)

    assert scanner.active_family_count == 0
    assert scanner.active_family_names == ()
    assert scanner.scan(_make_forecast(), _make_book()) == []


def test_data_only_family_appended_after_init_is_still_not_scanned():
    scanner = StrategyScanner(strategies=[])
    scanner.strategies.append(KalshiWeatherForecastStrategy())

    assert scanner.active_family_count == 0
    assert scanner.active_family_names == ()
    assert scanner.scan(_make_forecast(), _make_book()) == []


def test_equity_target_never_invokes_injected_proposal_strategy():
    class MustNotRun:
        name = "must_not_run"

        def evaluate(self, _forecast, _orderbook):
            raise AssertionError("equity target reached proposal strategy")

    forecast = _make_forecast().model_copy(
        update={
            "market_ticker": "KXTSLA-26JUL22-B350",
            "contract_ticker": "KXTSLA-26JUL22-B350",
        }
    )
    scanner = StrategyScanner(strategies=[MustNotRun()])

    assert scanner.scan(forecast, _make_book()) == []


def test_structured_equity_category_never_invokes_strategy_for_opaque_ticker():
    class MustNotRun:
        name = "must_not_run"

        def evaluate(self, _forecast, _orderbook):
            raise AssertionError("structured equity target reached strategy")

    scanner = StrategyScanner(strategies=[MustNotRun()])

    assert scanner.scan(
        _make_forecast(),
        _make_book(),
        market_category="Equities",
    ) == []
