from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Any

from core.ontology import NoTradeReason, StrategyCritique, TradeProposalDraft
from model_router.router import ModelRouter
from model_router.tasks import ModelTask
from strategies.critique import StrategyCritiqueEngine
from strategies.scan import StrategyScanner, StrategyScanResult


@dataclass
class IntelligenceResult:
    scan_result: StrategyScanResult
    critique: StrategyCritique | None = None
    no_trade_reason: NoTradeReason | None = None
    draft: TradeProposalDraft | None = None


class StrategyIntelligence:
    def __init__(
        self,
        scanner: StrategyScanner | None = None,
        critique_engine: StrategyCritiqueEngine | None = None,
        router: ModelRouter | None = None,
    ):
        self.router = router or ModelRouter()
        self.scanner = scanner or StrategyScanner()
        self.critique_engine = critique_engine or StrategyCritiqueEngine(self.router)

    async def evaluate(self, forecast: Any, orderbook: Any) -> list[IntelligenceResult]:
        scans = self.scanner.scan(forecast, orderbook)
        results: list[IntelligenceResult] = []
        for scan in scans:
            critique = await self.critique_engine.critique(scan)
            no_trade = None
            draft = None
            if scan.proposal is None:
                no_trade = await self._explain_no_trade(scan, forecast, critique)
            else:
                draft = TradeProposalDraft(
                    market_ticker=scan.proposal.market_ticker,
                    contract_ticker=scan.proposal.contract_ticker,
                    side=scan.proposal.side,
                    price_cents=scan.proposal.price_cents,
                    size=scan.proposal.size,
                    reasoning=critique.reasoning,
                    timestamp=datetime.now(timezone.utc),
                )
            results.append(IntelligenceResult(scan, critique, no_trade, draft))
        return results

    async def _explain_no_trade(
        self, scan: StrategyScanResult, forecast: Any, critique: StrategyCritique
    ) -> NoTradeReason:
        prompt = (
            f"Strategy {scan.family} returned no trade for {scan.market_ticker}. "
            f"Existing reason: {scan.no_trade_reason}. Critique: {critique.reasoning}. "
            "Return JSON with reason and contributing_factors."
        )
        envelope = await self.router.call(ModelTask.NO_TRADE_REASON, prompt)
        data = json.loads(envelope.content) if envelope.content else {}
        return NoTradeReason(
            market_ticker=scan.market_ticker,
            contract_ticker=scan.contract_ticker,
            reason=data.get("reason", scan.no_trade_reason or "unknown"),
            contributing_factors=data.get("contributing_factors", []),
            model_summary="hybrid_no_trade",
            timestamp=datetime.now(timezone.utc),
            proof_reference=envelope.proof_id,
        )
