import pytest

from strategies.critique import StrategyCritiqueEngine
from strategies.scan import StrategyScanResult


@pytest.mark.asyncio
async def test_critique_returns_structured_result():
    engine = StrategyCritiqueEngine()
    scan = StrategyScanResult(
        family="probability_disagreement",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        edge_estimate=0.01,
        confidence=0.6,
        liquidity_score=0.7,
        spread_score=0.8,
        settlement_risk_score=0.2,
    )
    critique = await engine.critique(scan)
    assert critique.strategy_family == "probability_disagreement"
    assert critique.market_ticker == "MKT"
    assert critique.contract_ticker == "MKT-YES"
    assert critique.verdict in {"proceed", "warn", "block"}
    assert critique.proof_reference
