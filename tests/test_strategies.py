from datetime import datetime, timezone
from decimal import Decimal
from core.ontology import OrderBook, OrderBookLevel
from forecasting.engine import ForecastEngine, kalshi_fee_cents, signed_edge_after_fees
from strategies.registry import STRATEGIES
from strategies.probability_disagreement import ProbabilityDisagreement
from risk.governor import assess_trade_risk
from core.config_loader import load_caps


def make_book():
    return OrderBook(
        market_ticker="M",
        contract_ticker="M-YES",
        bids=[OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=52, size=10)],
        timestamp=datetime.now(timezone.utc),
    )


def test_forecast_engine_produces_forecast():
    engine = ForecastEngine()
    f = engine.forecast("M", "M-YES", "Event", "Yes", make_book())
    assert f is not None
    assert f.market_ticker == "M"
    assert f.probability_delta == 0
    assert f.edge_after_fees == 0


def test_forecast_engine_uses_canonical_best_bid():
    book = OrderBook(
        market_ticker="M",
        contract_ticker="M-YES",
        bids=[OrderBookLevel(price=40, size=1), OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=52, size=10), OrderBookLevel(price=60, size=1)],
        timestamp=datetime.now(timezone.utc),
    )
    forecast = ForecastEngine().forecast("M", "M-YES", "Event", "Yes", book)
    assert forecast is not None
    assert forecast.market_implied_probability == Decimal("0.5")


def make_imbalanced_book():
    return OrderBook(
        market_ticker="M",
        contract_ticker="M-YES",
        bids=[OrderBookLevel(price=49, size=2000)],
        asks=[OrderBookLevel(price=51, size=1)],
        timestamp=datetime.now(timezone.utc),
    )


def make_negative_imbalanced_book():
    return OrderBook(
        market_ticker="M",
        contract_ticker="M-YES",
        bids=[OrderBookLevel(price=49, size=1)],
        asks=[OrderBookLevel(price=51, size=2000)],
        timestamp=datetime.now(timezone.utc),
    )


def test_forecast_engine_abstains_on_unusable_books():
    now = datetime.now(timezone.utc)
    empty = OrderBook(market_ticker="M", contract_ticker="M-YES", bids=[], asks=[], timestamp=now)
    crossed = OrderBook(
        market_ticker="M",
        contract_ticker="M-YES",
        bids=[OrderBookLevel(price=52, size=10)],
        asks=[OrderBookLevel(price=51, size=10)],
        timestamp=now,
    )
    engine = ForecastEngine()
    assert engine.forecast("M", "M-YES", "Event", "Yes", empty) is None
    assert engine.forecast("M", "M-YES", "Event", "Yes", crossed) is None


def test_kalshi_fee_is_nonlinear_and_rounds_up():
    assert kalshi_fee_cents(Decimal("0.50")) == 2
    assert kalshi_fee_cents(Decimal("0.10")) == 1
    assert kalshi_fee_cents(Decimal("0")) == 0


def test_fees_cannot_reverse_edge_direction():
    assert signed_edge_after_fees(Decimal("0.01"), Decimal("0.02")) == 0
    assert signed_edge_after_fees(Decimal("-0.01"), Decimal("0.02")) == 0
    assert signed_edge_after_fees(Decimal("-0.05"), Decimal("0.02")) == Decimal("-0.03")


def test_probability_disagreement_produces_proposal():
    engine = ForecastEngine()
    book = make_imbalanced_book()
    f = engine.forecast("M", "M-YES", "Event", "Yes", book)
    assert f is not None
    strat = ProbabilityDisagreement()
    p = strat.evaluate(f, book)
    assert p is not None
    assert p.side == "yes"
    assert p.edge_estimate.expected_edge_bps == int(abs(f.expected_edge) * Decimal("10000"))
    assert p.confidence_estimate == f.confidence_score


def test_probability_disagreement_can_produce_no_side():
    book = make_negative_imbalanced_book()
    forecast = ForecastEngine().forecast("M", "M-YES", "Event", "Yes", book)
    assert forecast is not None and forecast.probability_delta < Decimal("-0.02")
    proposal = ProbabilityDisagreement().evaluate(forecast, book)
    assert proposal is not None
    assert proposal.side == "no"
    assert proposal.price_cents == 51


def test_all_strategies_evaluate():
    engine = ForecastEngine()
    f = engine.forecast("M", "M-YES", "Event", "Yes", make_book())
    assert f is not None
    for strat in STRATEGIES:
        proposal = strat.evaluate(f, make_book())
        assert proposal is None or hasattr(proposal, "compliance_verdict")


def test_risk_governor_allows_safe_proposal():
    engine = ForecastEngine()
    book = make_imbalanced_book()
    f = engine.forecast("M", "M-YES", "Event", "Yes", book)
    assert f is not None
    p = ProbabilityDisagreement().evaluate(f, book)
    assert p is not None
    v = assess_trade_risk(p, load_caps())
    assert v.passed
