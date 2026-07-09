from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
import json

from core.ontology import StrategyCritique
from model_router.router import ModelRouter
from model_router.tasks import ModelTask
from strategies.scan import StrategyScanResult


class StrategyCritiqueEngine:
    def __init__(self, router: ModelRouter | None = None):
        self.router = router or ModelRouter()

    async def critique(self, result: StrategyScanResult) -> StrategyCritique:
        prompt = (
            f"Strategy: {result.family}\n"
            f"Market: {result.market_ticker}/{result.contract_ticker}\n"
            f"Edge estimate: {result.edge_estimate}\n"
            f"Confidence: {result.confidence}\n"
            f"Liquidity: {result.liquidity_score}, Spread: {result.spread_score}, Settlement risk: {result.settlement_risk_score}\n"
            "Return JSON with verdict (proceed/warn/block), edge_assessment, risk_assessment, confidence_adjustment, reasoning."
        )
        envelope = await self.router.call(ModelTask.STRATEGY_CRITIQUE, prompt)
        data = json.loads(envelope.content) if envelope.content else {}
        return StrategyCritique(
            strategy_family=result.family,
            market_ticker=result.market_ticker,
            contract_ticker=result.contract_ticker,
            verdict=data.get("verdict", "warn"),
            edge_assessment=data.get("edge_assessment", ""),
            risk_assessment=data.get("risk_assessment", ""),
            confidence_adjustment=Decimal(str(data.get("confidence_adjustment", 0))),
            reasoning=data.get("reasoning", ""),
            timestamp=datetime.now(timezone.utc),
            proof_reference=envelope.proof_id,
        )
