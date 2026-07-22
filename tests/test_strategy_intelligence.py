from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.ontology import ComplianceVerdict, EdgeEstimate, OrderBook, OrderBookLevel, TradeProposal
from forecasting.engine import ForecastEngine
from strategies.intelligence import StrategyIntelligence
from strategies.scan import StrategyScanner


def make_book():
    return OrderBook(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        bids=[OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=52, size=10)],
        timestamp=datetime.now(timezone.utc),
    )


def make_forecast():
    return ForecastEngine().forecast("MKT", "MKT-YES", "Event", "Yes", make_book())


class AlwaysPropose:
    name = "always_propose"
    PREDICTION_AUTHORITY = True

    def evaluate(self, forecast, orderbook):
        return TradeProposal(
            id="test_1",
            market_ticker=forecast.market_ticker,
            contract_ticker=forecast.contract_ticker,
            side="yes",
            price_cents=50,
            size=1,
            forecast_reference=forecast.proof_reference,
            edge_estimate=EdgeEstimate(
                expected_edge_bps=150, edge_after_fees_bps=100, confidence_score=Decimal("0.6")
            ),
            risk_estimate="low",
            confidence_estimate=Decimal("0.6"),
            expected_fill_behavior="passive limit fill",
            stop_condition="edge evaporates",
            cancellation_condition="stale quote",
            cap_impact={},
            compliance_verdict=ComplianceVerdict(passed=True, blocked_categories=[], reason="ok"),
            proof_reference="proof_1",
        )


class NeverPropose:
    name = "never_propose"
    PREDICTION_AUTHORITY = True

    def evaluate(self, forecast, orderbook):
        return None


@pytest.mark.asyncio
async def test_intelligence_produces_draft_for_proposal():
    scanner = StrategyScanner(strategies=[AlwaysPropose()])
    intelligence = StrategyIntelligence(scanner=scanner)
    forecast, book = make_forecast(), make_book()
    results = await intelligence.evaluate(forecast, book)
    assert len(results) == 1
    result = results[0]
    assert result.critique is not None
    assert result.draft is not None
    assert result.draft.market_ticker == "MKT"
    assert result.no_trade_reason is None


@pytest.mark.asyncio
async def test_intelligence_produces_no_trade_reason_for_empty_proposal():
    scanner = StrategyScanner(strategies=[NeverPropose()])
    intelligence = StrategyIntelligence(scanner=scanner)
    forecast, book = make_forecast(), make_book()
    results = await intelligence.evaluate(forecast, book)
    assert len(results) == 1
    result = results[0]
    assert result.critique is not None
    assert result.draft is None
    assert result.no_trade_reason is not None
    assert result.no_trade_reason.market_ticker == "MKT"
    assert result.no_trade_reason.proof_reference
