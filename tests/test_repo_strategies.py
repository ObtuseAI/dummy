import ast
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pytest

from core.ontology import Forecast, OrderBook, OrderBookLevel, TradeProposal
from strategies.repo_derived import (
    CommoditiesEnergyStrategy,
    CryptoEventMarketStrategy,
    KalshiWeatherForecastStrategy,
    OrderbookSpreadCaptureStrategy,
    RepoDerivedCrossMarketArbitrage,
    SportsMomentumStrategy,
    StaleQuoteDetectionStrategy,
    StockMacroMomentumStrategy,
)
from strategies.registry import (
    ACTIVE_REPO_DERIVED_FAMILY_COUNT,
    ACTIVE_REPO_DERIVED_FAMILY_NAMES,
    STRATEGIES,
    get_repo_derived_strategies,
)


REPO_DERIVED_CLASSES = [
    KalshiWeatherForecastStrategy,
    SportsMomentumStrategy,
    CryptoEventMarketStrategy,
    StockMacroMomentumStrategy,
    CommoditiesEnergyStrategy,
    RepoDerivedCrossMarketArbitrage,
    OrderbookSpreadCaptureStrategy,
    StaleQuoteDetectionStrategy,
]

NON_AUTHORITATIVE_CLASSES = [
    KalshiWeatherForecastStrategy,
    StockMacroMomentumStrategy,
    CommoditiesEnergyStrategy,
]

ACTIVE_REPO_DERIVED_CLASSES = [
    cls for cls in REPO_DERIVED_CLASSES if cls not in NON_AUTHORITATIVE_CLASSES
]

REPO_DERIVED_DIR = Path(__file__).parent.parent / "strategies" / "repo_derived"


def _make_book(
    bids: Optional[list[tuple[int, int]]] = None,
    asks: Optional[list[tuple[int, int]]] = None,
) -> OrderBook:
    return OrderBook(
        market_ticker="WEATHER-NYC-2026-07-01",
        contract_ticker="WEATHER-NYC-2026-07-01-YES",
        bids=[OrderBookLevel(price=p, size=s) for p, s in (bids or [(48, 10)])],
        asks=[OrderBookLevel(price=p, size=s) for p, s in (asks or [(52, 10)])],
        timestamp=datetime.now(timezone.utc),
    )


def _make_forecast(
    probability_delta: Decimal = Decimal("0.08"),
    confidence_score: Decimal = Decimal("0.75"),
    freshness_score: Decimal = Decimal("0.85"),
    settlement_risk_score: Decimal = Decimal("0.2"),
) -> Forecast:
    return Forecast(
        market_ticker="WEATHER-NYC-2026-07-01",
        contract_ticker="WEATHER-NYC-2026-07-01-YES",
        event_title="NYC High Temp",
        contract_title=">80F",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.58"),
        probability_delta=probability_delta,
        confidence_score=confidence_score,
        uncertainty_band=(Decimal("0.5"), Decimal("0.65")),
        expected_edge=Decimal("0.012"),
        edge_after_fees=Decimal("0.008"),
        freshness_score=freshness_score,
        liquidity_score=Decimal("0.8"),
        spread_score=Decimal("0.8"),
        orderbook_depth_score=Decimal("0.8"),
        settlement_risk_score=settlement_risk_score,
        source_summary="test",
        model_summary="repo-derived-test",
        calibration_notes="test",
        timestamp=datetime.now(timezone.utc),
        expiration=datetime.now(timezone.utc) + timedelta(hours=1),
        strategy_references=[],
        proof_reference="forecast-test-123",
    )


@pytest.mark.parametrize("cls", REPO_DERIVED_CLASSES)
def test_repo_derived_strategy_imports_and_subclasses_genome(cls):
    from strategies.genome_base import StrategyGenome

    assert issubclass(cls, StrategyGenome)
    assert cls().name is not None


@pytest.mark.parametrize("cls", REPO_DERIVED_CLASSES)
def test_repo_derived_strategy_evaluates_without_error(cls):
    strat = cls()
    proposal = strat.evaluate(_make_forecast(), _make_book())
    assert proposal is None or isinstance(proposal, TradeProposal)


@pytest.mark.parametrize("cls", REPO_DERIVED_CLASSES)
def test_repo_derived_strategy_returns_none_when_edge_too_small(cls):
    strat = cls()
    forecast = _make_forecast(probability_delta=Decimal("0.005"))
    proposal = strat.evaluate(forecast, _make_book())
    assert proposal is None


@pytest.mark.parametrize("cls", ACTIVE_REPO_DERIVED_CLASSES)
def test_repo_derived_strategy_returns_trade_proposal_when_edge_strong(cls):
    strat = cls()
    # Stale quote detection needs freshness <= 0.9; set explicitly.
    freshness = Decimal("0.85") if cls is StaleQuoteDetectionStrategy else Decimal("0.95")
    forecast = _make_forecast(
        probability_delta=Decimal("0.08"),
        confidence_score=Decimal("0.75"),
        freshness_score=freshness,
        settlement_risk_score=Decimal("0.2"),
    )
    proposal = strat.evaluate(forecast, _make_book())
    assert isinstance(proposal, TradeProposal)
    assert proposal.forecast_reference == forecast.proof_reference
    assert proposal.compliance_verdict is not None
    assert proposal.cap_impact is not None
    assert "liquidity_estimate" in proposal.cap_impact
    assert "spread_estimate_cents" in proposal.cap_impact
    assert "settlement_risk_estimate" in proposal.cap_impact


@pytest.mark.parametrize("cls", REPO_DERIVED_CLASSES)
def test_repo_derived_strategy_respects_empty_orderbook(cls):
    strat = cls()
    empty_book = OrderBook(
        market_ticker="WEATHER-NYC-2026-07-01",
        contract_ticker="WEATHER-NYC-2026-07-01-YES",
        bids=[],
        asks=[],
        timestamp=datetime.now(timezone.utc),
    )
    assert strat.evaluate(_make_forecast(), empty_book) is None


def test_registry_contains_all_repo_derived_strategies():
    names = {s.name for s in STRATEGIES}
    expected = {cls().name for cls in ACTIVE_REPO_DERIVED_CLASSES}
    assert expected.issubset(names), f"Missing: {expected - names}"


def test_active_repo_derived_catalog_matches_prediction_authority():
    active = get_repo_derived_strategies()
    assert tuple(strategy.name for strategy in active) == ACTIVE_REPO_DERIVED_FAMILY_NAMES
    assert len(active) == ACTIVE_REPO_DERIVED_FAMILY_COUNT == 5
    assert all(not strategy.DATA_ONLY for strategy in active)
    assert all(strategy.PREDICTION_AUTHORITY for strategy in active)


@pytest.mark.parametrize(
    "cls", [KalshiWeatherForecastStrategy, CommoditiesEnergyStrategy]
)
def test_weather_and_commodities_are_unregistered_data_only_abstainers(cls):
    strategy = cls()
    assert strategy.DATA_ONLY is True
    assert strategy.PREDICTION_AUTHORITY is False
    assert strategy.evaluate(_make_forecast(), _make_book()) is None
    assert strategy.name not in {item.name for item in STRATEGIES}


def test_stock_macro_strategy_is_permanently_excluded():
    strategy = StockMacroMomentumStrategy()

    assert strategy.DATA_ONLY is False
    assert strategy.PREDICTION_AUTHORITY is False
    assert strategy.QUARANTINE_REASON == "outside_supported_prediction_targets"
    assert strategy.evaluate(_make_forecast(), _make_book()) is None
    assert strategy.name not in {item.name for item in STRATEGIES}
    assert strategy.name not in ACTIVE_REPO_DERIVED_FAMILY_NAMES


def test_no_repo_derived_strategy_calls_live_order_endpoints():
    """Statically prove repo_derived strategy modules never invoke live order endpoints."""
    forbidden = {
        "create_order",
        "submit_order",
        "place_order",
        "post_order",
        "send_order",
        "buy",
        "sell",
    }
    for path in REPO_DERIVED_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                assert name not in forbidden, (
                    f"{path.name} calls forbidden live-order function: {name}"
                )


def test_repo_derived_strategies_use_only_trade_proposal_output():
    """Runtime proof: every repo-derived strategy returns TradeProposal or None."""
    book = _make_book()
    forecast = _make_forecast()
    for cls in REPO_DERIVED_CLASSES:
        proposal = cls().evaluate(forecast, book)
        assert proposal is None or isinstance(proposal, TradeProposal)
