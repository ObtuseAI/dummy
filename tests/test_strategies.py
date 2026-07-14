from datetime import datetime, timezone
from core.ontology import OrderBook, OrderBookLevel
from forecasting.engine import ForecastEngine
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
    assert f.market_ticker == "M"
    assert f.probability_delta != 0


def test_probability_disagreement_produces_proposal():
    engine = ForecastEngine()
    f = engine.forecast("M", "M-YES", "Event", "Yes", make_book())
    strat = ProbabilityDisagreement()
    p = strat.evaluate(f, make_book())
    assert p is not None
    assert p.side == "yes"


def test_all_strategies_evaluate():
    engine = ForecastEngine()
    f = engine.forecast("M", "M-YES", "Event", "Yes", make_book())
    for strat in STRATEGIES:
        proposal = strat.evaluate(f, make_book())
        assert proposal is None or hasattr(proposal, "compliance_verdict")


def test_risk_governor_allows_safe_proposal():
    engine = ForecastEngine()
    f = engine.forecast("M", "M-YES", "Event", "Yes", make_book())
    p = ProbabilityDisagreement().evaluate(f, make_book())
    v = assess_trade_risk(p, load_caps())
    assert v.passed
