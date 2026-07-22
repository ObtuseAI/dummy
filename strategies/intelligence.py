from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
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

    async def evaluate(
        self,
        forecast: Any,
        orderbook: Any,
        *,
        market_category: str | None = None,
    ) -> list[IntelligenceResult]:
        scans = self.scanner.scan(
            forecast,
            orderbook,
            market_category=market_category,
        )
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

    def evaluate_quant_only(
        self,
        forecast: Any,
        orderbook: Any,
        *,
        market_category: str | None = None,
    ) -> list[IntelligenceResult]:
        """Run deterministic strategy scans without any model call or verdict.

        This is the only admissible strategy-intelligence path while the
        exact market scope has zero model authority.  It preserves quantitative
        proposals/no-trade explanations without letting a live or fallback LLM
        grant approval, confidence, or veto authority.
        """
        results: list[IntelligenceResult] = []
        for scan in self.scanner.scan(
            forecast,
            orderbook,
            market_category=market_category,
        ):
            critique = StrategyCritique(
                strategy_family=scan.family,
                market_ticker=scan.market_ticker,
                contract_ticker=scan.contract_ticker,
                verdict="proceed",
                edge_assessment="quantitative scan only",
                risk_assessment="model critique excluded because authority is zero",
                reasoning="neutral deterministic critique; no model output consumed",
                timestamp=datetime.now(timezone.utc),
                proof_reference=(
                    f"quant_only_critique_{scan.market_ticker}_{scan.contract_ticker}"
                ),
            )
            no_trade = None
            draft = None
            if scan.proposal is None:
                no_trade = NoTradeReason(
                    market_ticker=scan.market_ticker,
                    contract_ticker=scan.contract_ticker,
                    reason=scan.no_trade_reason or "quantitative strategy abstained",
                    contributing_factors=["quant_only_model_authority_zero"],
                    model_summary="quant_only",
                    timestamp=datetime.now(timezone.utc),
                    proof_reference=f"quant_only_no_trade_{scan.market_ticker}_{scan.contract_ticker}",
                )
            else:
                draft = TradeProposalDraft(
                    market_ticker=scan.proposal.market_ticker,
                    contract_ticker=scan.proposal.contract_ticker,
                    side=scan.proposal.side,
                    price_cents=scan.proposal.price_cents,
                    size=scan.proposal.size,
                    reasoning="quantitative strategy proposal; model authority zero",
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
