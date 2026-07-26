from datetime import datetime, timedelta, timezone
from decimal import Decimal

from core.config_loader import load_caps
from core.ontology import Forecast, OrderBook, OrderBookLevel
from forecasting.fees import kalshi_fee_cents, signed_edge_after_fees
from risk.governor import assess_trade_risk
from strategies.probability_disagreement import ProbabilityDisagreement
from strategies.registry import STRATEGIES


def make_book() -> OrderBook:
    return OrderBook(
        market_ticker="M",
        contract_ticker="M-YES",
        bids=[OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=52, size=10)],
        timestamp=datetime.now(timezone.utc),
    )


def make_forecast(delta: Decimal = Decimal("0")) -> Forecast:
    now = datetime.now(timezone.utc)
    implied = Decimal("0.5")
    probability = implied + delta
    fee = Decimal(kalshi_fee_cents(implied)) / Decimal("100")
    return Forecast(
        market_ticker="M",
        contract_ticker="M-YES",
        event_title="Event",
        contract_title="Yes",
        market_implied_probability=implied,
        dummy_probability=probability,
        probability_delta=delta,
        confidence_score=Decimal("0.8"),
        uncertainty_band=(
            max(Decimal("0"), probability - Decimal("0.05")),
            min(Decimal("1"), probability + Decimal("0.05")),
        ),
        expected_edge=delta,
        edge_after_fees=signed_edge_after_fees(delta, fee),
        freshness_score=Decimal("1"),
        liquidity_score=Decimal("0.8"),
        spread_score=Decimal("0.8"),
        orderbook_depth_score=Decimal("0.8"),
        settlement_risk_score=Decimal("0.2"),
        source_summary="test_evidence",
        model_summary="test_forecast_factory",
        calibration_notes="test",
        timestamp=now,
        expiration=now + timedelta(hours=1),
        strategy_references=[],
        proof_reference=f"test-forecast-{delta}",
    )


def test_kalshi_fee_is_nonlinear_and_rounds_up():
    assert kalshi_fee_cents(Decimal("0.50")) == 2
    assert kalshi_fee_cents(Decimal("0.10")) == 1
    assert kalshi_fee_cents(Decimal("0")) == 0


def test_fees_cannot_reverse_edge_direction():
    assert signed_edge_after_fees(Decimal("0.01"), Decimal("0.02")) == 0
    assert signed_edge_after_fees(Decimal("-0.01"), Decimal("0.02")) == 0
    assert signed_edge_after_fees(
        Decimal("-0.05"), Decimal("0.02")
    ) == Decimal("-0.03")


def test_probability_disagreement_produces_yes_proposal():
    forecast = make_forecast(Decimal("0.05"))
    proposal = ProbabilityDisagreement().evaluate(forecast, make_book())

    assert proposal is not None
    assert proposal.side == "yes"
    assert proposal.edge_estimate.expected_edge_bps == 500
    assert proposal.confidence_estimate == forecast.confidence_score


def test_probability_disagreement_can_produce_no_side():
    forecast = make_forecast(Decimal("-0.05"))
    proposal = ProbabilityDisagreement().evaluate(forecast, make_book())

    assert proposal is not None
    assert proposal.side == "no"
    assert proposal.price_cents == 52


def test_all_catalogued_research_strategies_evaluate():
    forecast = make_forecast()
    for strategy in STRATEGIES:
        proposal = strategy.evaluate(forecast, make_book())
        assert proposal is None or hasattr(proposal, "compliance_verdict")


def test_risk_governor_allows_safe_proposal():
    proposal = ProbabilityDisagreement().evaluate(
        make_forecast(Decimal("0.05")),
        make_book(),
    )
    assert proposal is not None
    assert assess_trade_risk(proposal, load_caps()).passed
