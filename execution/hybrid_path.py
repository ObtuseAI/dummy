from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from execution.autonomous_path import AutonomousExecutionPath
from forecasting.hybrid_engine import HybridForecastEngine
from forecasting.real_market_loop import RealMarketForecastLoopV2
from kalshi.live_data import KalshiCredentialsMissing, KalshiLiveData
from live_firewall.firewall import LiveBrokerFirewall
from live_firewall.exposure_tracker import ExposureTracker
from model_router.tasks import ModelTask
from strategies.disagreement import HybridDisagreementEngine, HybridDisagreementEngineV2
from strategies.governor import (
    CapImpact,
    GovernorDecision,
    MarketQualityScores,
    RiskCritique,
    StrategyGovernor,
)
from strategies.intelligence import StrategyIntelligence
from compliance.governor import assess_compliance
from risk.governor import assess_trade_risk
from core import state as state_module
from core.config_loader import load_caps
from core.ontology import (
    AccountMode,
    ComplianceVerdict,
    Forecast,
    ForecastOpinion,
    LiveOrderRequest,
    NoTradeReason,
    OrderBook,
    TradeProposal,
)
from proof.ledger import write_proof


class HybridAutonomousExecutionPath(AutonomousExecutionPath):
    def __init__(self, *args, hybrid_engine: HybridForecastEngine | None = None, intelligence: StrategyIntelligence | None = None, disagreement: HybridDisagreementEngine | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.hybrid_engine = hybrid_engine or HybridForecastEngine()
        self.intelligence = intelligence or StrategyIntelligence()
        self.disagreement = disagreement or HybridDisagreementEngine()

    async def rehearse_live_cap_with_model_review(
        self,
        market_ticker: str,
        contract_ticker: str,
        strategy_name: str | None = None,
    ) -> dict[str, Any]:
        if state_module.STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
            return {"status": "blocked", "rejected_by": "mode", "reason": "Mode is not AUTONOMOUS_LIVE_CAPPED"}
        base = await super().rehearse_live_cap(market_ticker, contract_ticker, strategy_name)
        if base.get("status") in ("blocked", "no_trade") or "proposal" not in base:
            return {**base, "model_review": None}

        proposal = base["proposal"]
        orderbook = base.get("orderbook")
        forecast_opinion = None
        if orderbook:
            forecast_opinion = await self.hybrid_engine.forecast_opinion(
                market_ticker=market_ticker,
                contract_ticker=contract_ticker,
                event_title=market_ticker,
                contract_title=contract_ticker,
                orderbook=orderbook,
            )
        intelligence_results = []
        if orderbook and "forecast" in base:
            from core.ontology import Forecast
            forecast = Forecast.model_validate(base["forecast"])
            intelligence_results = await self.intelligence.evaluate(forecast, orderbook)

        review = None
        if forecast_opinion:
            review = await self.disagreement.review(
                ModelTask.FORECAST_OPINION,
                f"Review forecast for {market_ticker}",
                context={"market_ticker": market_ticker, "contract_ticker": contract_ticker},
            )

        model_review = {
            "forecast_opinion": forecast_opinion.model_dump() if forecast_opinion else None,
            "intelligence_results": [self._intelligence_to_dict(r) for r in intelligence_results],
            "disagreement_review": review,
        }
        return {**base, "model_review": model_review, "hybrid_status": base.get("status")}

    def _intelligence_to_dict(self, result) -> dict[str, Any]:
        return {
            "family": result.scan_result.family,
            "critique_verdict": result.critique.verdict if result.critique else None,
            "no_trade_reason": result.no_trade_reason.reason if result.no_trade_reason else None,
            "draft": result.draft.model_dump() if result.draft else None,
        }


class _RealMarketForecastLoopV2WithDetails(RealMarketForecastLoopV2):
    """Run the V2 real-market forecast loop and return raw market details.

    This subclass exposes the market, contract, orderbook, base forecast and
    hybrid review for a single contract so that the V2 rehearsal path can feed
    them into the strategy governor and the live firewall.
    """

    async def run_for_contract(
        self,
        contract_ticker: str,
        max_markets: int = 5,
    ) -> dict[str, Any] | None:
        self.model_mode = self._determine_model_mode()
        reader = None
        try:
            reader = self._reader_cls()
            self.credentials_present = True
        except KalshiCredentialsMissing:
            self.credentials_present = False

        entries: list[tuple[Any, Any, OrderBook, dict[str, Any]]] = []
        snapshot_source = "live"
        try:
            if reader is None:
                snapshot_source = "mock"
                mock_entries = self._mock_market_data()
                entries = self._select_from_scored(
                    [
                        (market, contract, book, self._score_market(market, contract, book))
                        for market, contract, book in mock_entries
                    ],
                    max_markets,
                )
            else:
                entries = await self._fetch_live_market_data(reader, max_markets)
                # If live data does not include the requested contract, fall back
                # to mock data so the rehearsal can still exercise the firewall
                # and no-live-submit gates deterministically.
                if not any(contract.ticker == contract_ticker for _m, contract, _b, _s in entries):
                    snapshot_source = "mock"
                    mock_entries = self._mock_market_data()
                    entries = self._select_from_scored(
                        [
                            (market, contract, book, self._score_market(market, contract, book))
                            for market, contract, book in mock_entries
                        ],
                        max_markets,
                    )
        finally:
            if reader is not None:
                await reader.close()

        for market, contract, orderbook, scores in entries:
            if contract.ticker != contract_ticker:
                continue
            base = self._build_base_forecast(market, contract, orderbook, scores)
            review = await self.hybrid_engine.hybrid_review(
                base=base,
                orderbook=orderbook,
                market=market,
                contract=contract,
                scores=scores,
                model_mode=self.model_mode,
            )
            opinion = self._synthesize_opinion(base, scores, review)
            return {
                "source": snapshot_source,
                "model_mode": self.model_mode,
                "credentials_present": self.credentials_present,
                "market": market,
                "contract": contract,
                "orderbook": orderbook,
                "scores": scores,
                "base_forecast": base,
                "review": review,
                "opinion": opinion,
            }
        return None

    @property
    def _reader_cls(self):
        from kalshi.live_data import KalshiRealReadOnly

        return KalshiRealReadOnly


class HybridLiveCapRehearsalV2:
    """V2 live-capped firewall rehearsal with strategy-governor integration.

    The chain is:

        real Kalshi data -> RealMarketForecastLoopV2 -> hybrid model review
        -> HybridDisagreementEngineV2 -> StrategyGovernor
        -> TradeProposal | NoTradeReason -> risk/compliance gates
        -> LiveBrokerFirewall.submit_rehearsal

    By default the chain stops at the firewall rehearsal.  A real order is only
    sent when ``configs/live_submit.json`` is enabled *and* every safety gate
    (limit order, caps, kill switch, emergency stop, proof refs, secret
    redaction, compliance, strategy-governor approval) passes.
    """

    DEFAULT_ADAPTER_NAME = "kalshi_live_firewall_adapter"
    PROJECT_ROOT = Path(__file__).parent.parent

    def __init__(
        self,
        loop: _RealMarketForecastLoopV2WithDetails | None = None,
        intelligence: StrategyIntelligence | None = None,
        governor: StrategyGovernor | None = None,
        disagreement: HybridDisagreementEngineV2 | None = None,
        firewall: LiveBrokerFirewall | None = None,
        exposure: ExposureTracker | None = None,
        live_data: KalshiLiveData | None = None,
        adapter_name: str = DEFAULT_ADAPTER_NAME,
    ):
        self.loop = loop or _RealMarketForecastLoopV2WithDetails()
        self.intelligence = intelligence or StrategyIntelligence()
        self.governor = governor or StrategyGovernor()
        self.disagreement = disagreement or HybridDisagreementEngineV2()
        self.exposure = exposure or ExposureTracker()
        self.live_data = live_data or KalshiLiveData()
        self.firewall = firewall or LiveBrokerFirewall(self.live_data.client, self.exposure)
        self.adapter_name = adapter_name

    async def rehearse(
        self,
        market_ticker: str,
        contract_ticker: str,
        strategy_name: str | None = None,
    ) -> dict[str, Any]:
        base_payload = {
            "market_ticker": market_ticker,
            "contract_ticker": contract_ticker,
            "strategy_name": strategy_name,
            "mode": state_module.STATE.mode.value,
            "adapter_name": self.adapter_name,
        }

        if state_module.STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
            payload = {
                **base_payload,
                "status": "blocked",
                "rejected_by": "mode",
                "reason": "Mode is not AUTONOMOUS_LIVE_CAPPED",
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}

        details = await self.loop.run_for_contract(contract_ticker)
        if details is None:
            payload = {
                **base_payload,
                "status": "no_trade",
                "reason": f"No market data available for {contract_ticker}",
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "no_trade", payload)
            return {**payload, "proof_reference": proof_ref}

        opinion: ForecastOpinion = details["opinion"]
        orderbook: OrderBook = details["orderbook"]
        base_forecast: Forecast = details["base_forecast"]
        review: dict[str, Any] = details["review"]

        # The hybrid model review may revise the base forecast.  Reflect the
        # reviewed opinion in the forecast used by the firewall so the edge gate
        # is evaluated against the model consensus rather than the raw mid.
        base_forecast.market_implied_probability = opinion.market_implied_probability
        base_forecast.dummy_probability = opinion.dummy_probability
        base_forecast.probability_delta = opinion.probability_delta
        base_forecast.expected_edge = opinion.probability_delta
        base_forecast.edge_after_fees = max(Decimal("0"), opinion.probability_delta - Decimal("0.005"))
        base_forecast.confidence_score = opinion.confidence_score

        intelligence_results = await self.intelligence.evaluate(base_forecast, orderbook)
        selected = self._select_intelligence_result(intelligence_results, strategy_name)

        strategy_critique = selected.critique if selected else None
        risk_critique = self._risk_critique_from_review(review)

        disagreement = await self.disagreement.review(
            opinion=opinion,
            strategy_signal={"verdict": strategy_critique.verdict} if strategy_critique else None,
            risk_governor_value={"risk_level": risk_critique.risk_level} if risk_critique else None,
            calibration_confidence=opinion.confidence_score,
            context={"market_ticker": market_ticker, "contract_ticker": contract_ticker},
        )

        proposal = self._derive_trade_decision(
            market_ticker,
            contract_ticker,
            opinion,
            orderbook,
            selected,
        )

        caps = load_caps()
        compliance_verdict = assess_compliance(market_ticker, contract_ticker, caps=caps)
        quality_scores = MarketQualityScores.from_opinion(opinion)
        cap_impact = self._compute_cap_impact(proposal, caps)

        governor_output = self.governor.evaluate(
            opinion=opinion,
            strategy_critique=strategy_critique,
            risk_critique=risk_critique,
            quality_scores=quality_scores,
            calibration_confidence=float(opinion.confidence_score),
            disagreement_score=float(disagreement["disagreement_score"]),
            cap_impact=cap_impact,
            compliance_verdict=compliance_verdict,
            model_output_firewall_blocked=False,
        )

        if governor_output.decision != GovernorDecision.APPROVE_FOR_FIREWALL_REHEARSAL:
            no_trade = NoTradeReason(
                market_ticker=market_ticker,
                contract_ticker=contract_ticker,
                reason=governor_output.reason,
                contributing_factors=governor_output.blocked_by or ["governor_rejection"],
                model_summary=opinion.model_summary,
                timestamp=datetime.now(timezone.utc),
                proof_reference=governor_output.proof_reference,
            )
            payload = {
                **base_payload,
                "status": "no_trade",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "governor",
                "reason": governor_output.reason,
                "forecast_opinion": opinion.model_dump(),
                "strategy_governor_decision": governor_output.decision.value,
                "disagreement": disagreement,
                "no_trade_reason": no_trade.model_dump(),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "no_trade", payload)
            return {**payload, "proof_reference": proof_ref}

        if proposal is None:
            proposal = self._synthesize_proposal(market_ticker, contract_ticker, opinion, orderbook)
        if proposal is None:
            no_trade = NoTradeReason(
                market_ticker=market_ticker,
                contract_ticker=contract_ticker,
                reason="Governor approved but no TradeProposal could be derived",
                contributing_factors=["no_proposal"],
                model_summary=opinion.model_summary,
                timestamp=datetime.now(timezone.utc),
                proof_reference=governor_output.proof_reference,
            )
            payload = {
                **base_payload,
                "status": "no_trade",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "proposal_derivation",
                "reason": no_trade.reason,
                "forecast_opinion": opinion.model_dump(),
                "strategy_governor_decision": governor_output.decision.value,
                "disagreement": disagreement,
                "no_trade_reason": no_trade.model_dump(),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "no_trade", payload)
            return {**payload, "proof_reference": proof_ref}

        proposal.compliance_verdict = compliance_verdict
        risk_verdict = assess_trade_risk(proposal, caps)
        if not risk_verdict.passed:
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "risk",
                "reason": risk_verdict.reason,
                "forecast_opinion": opinion.model_dump(),
                "strategy_governor_decision": governor_output.decision.value,
                "disagreement": disagreement,
                "proposal": proposal.model_dump(),
                "risk_verdict": risk_verdict.model_dump(),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}

        request = LiveOrderRequest(
            proposal_id=proposal.id,
            market_ticker=proposal.market_ticker,
            contract_ticker=proposal.contract_ticker,
            side=proposal.side,
            price_cents=proposal.price_cents,
            size=proposal.size,
            strategy_proof_reference=proposal.proof_reference,
            forecast_proof_reference=opinion.proof_reference,
            adapter_name=self.adapter_name,
        )

        if not request.strategy_proof_reference or not request.forecast_proof_reference:
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "proof",
                "reason": "Missing strategy or forecast proof reference",
                "forecast_opinion": opinion.model_dump(),
                "strategy_governor_decision": governor_output.decision.value,
                "proposal": proposal.model_dump(),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}

        firewall_rehearsal = await self.firewall.submit_rehearsal(request, orderbook, base_forecast)

        live_submitted = False
        order_result = None
        if firewall_rehearsal.would_submit and self.firewall._live_submit_enabled():
            order_result = await self.firewall.submit(request, orderbook, base_forecast)
            live_submitted = order_result.success

        if firewall_rehearsal.would_submit:
            status = "live_submitted" if live_submitted else "rehearsal"
        elif firewall_rehearsal.blocked_reason == "live_submit_disabled":
            status = "rehearsal"
        else:
            status = "blocked"

        payload: dict[str, Any] = {
            **base_payload,
            "status": status,
            "source": details["source"],
            "model_mode": details["model_mode"],
            "credentials_present": details["credentials_present"],
            "forecast_opinion": opinion.model_dump(),
            "strategy_governor_decision": governor_output.decision.value,
            "disagreement": disagreement,
            "proposal": proposal.model_dump(),
            "compliance_verdict": compliance_verdict.model_dump(),
            "risk_verdict": risk_verdict.model_dump(),
            "firewall_rehearsal": {
                "would_submit": firewall_rehearsal.would_submit,
                "blocked_reason": firewall_rehearsal.blocked_reason,
                "order": firewall_rehearsal.order,
            },
            "would_submit": firewall_rehearsal.would_submit,
            "blocked_reason": firewall_rehearsal.blocked_reason,
            "live_submitted": live_submitted,
            "order_result": order_result.model_dump() if order_result else None,
        }
        if status == "blocked":
            payload["rejected_by"] = "firewall"
            payload["reason"] = firewall_rehearsal.blocked_reason
        proof_ref = write_proof("rehearse_live_cap_v2", payload["status"], payload)
        return {**payload, "proof_reference": proof_ref}

    def _select_intelligence_result(
        self,
        results: list[Any],
        strategy_name: str | None,
    ) -> Any | None:
        if strategy_name is not None:
            matched = [r for r in results if r.scan_result.family == strategy_name]
            if matched:
                return matched[0]
        for r in results:
            if r.scan_result.proposal is not None:
                return r
        return results[0] if results else None

    def _derive_trade_decision(
        self,
        market_ticker: str,
        contract_ticker: str,
        opinion: ForecastOpinion,
        orderbook: OrderBook,
        selected: Any | None,
    ) -> TradeProposal | None:
        if selected is not None and selected.scan_result.proposal is not None:
            return selected.scan_result.proposal
        return self._synthesize_proposal(market_ticker, contract_ticker, opinion, orderbook)

    def _synthesize_proposal(
        self,
        market_ticker: str,
        contract_ticker: str,
        opinion: ForecastOpinion,
        orderbook: OrderBook,
    ) -> TradeProposal | None:
        side = "yes" if opinion.probability_delta >= Decimal("0") else "no"
        if side == "yes":
            price = orderbook.asks[0].price if orderbook.asks else 50
        else:
            price = 100 - (orderbook.bids[-1].price if orderbook.bids else 50)
        size = 1
        from core.ontology import EdgeEstimate

        edge_bps = max(0, int(float(opinion.probability_delta) * 10000))
        return TradeProposal(
            id=f"v2_governor_{market_ticker}_{contract_ticker}_{datetime.now(timezone.utc).isoformat()}",
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            side=side,
            price_cents=price,
            size=size,
            forecast_reference=opinion.forecast_reference,
            edge_estimate=EdgeEstimate(
                expected_edge_bps=edge_bps,
                edge_after_fees_bps=max(0, edge_bps - 50),
                confidence_score=opinion.confidence_score,
            ),
            risk_estimate="low" if opinion.confidence_score >= Decimal("0.5") else "medium",
            confidence_estimate=opinion.confidence_score,
            expected_fill_behavior="passive limit fill",
            stop_condition="edge evaporates or governor recall",
            cancellation_condition="stale quote > 30s or governor recall",
            cap_impact={"single_order_cents": price * size},
            compliance_verdict=ComplianceVerdict(passed=True, blocked_categories=[], reason=""),
            proof_reference=f"strategy_v2_governor_{opinion.proof_reference}",
        )

    def _risk_critique_from_review(self, review: dict[str, Any]) -> RiskCritique:
        risk_envelope = review.get("risk")
        if risk_envelope is None or not risk_envelope.content:
            return RiskCritique()
        try:
            data = json.loads(risk_envelope.content)
        except Exception:
            data = {}
        return RiskCritique(
            verdict="proceed" if str(data.get("risk_level", "")).lower() == "low" else "warn",
            risk_level=str(data.get("risk_level", "medium")).lower(),
            reasoning=data.get("reasoning", ""),
            proof_reference=getattr(risk_envelope, "proof_id", ""),
        )

    def _compute_cap_impact(self, proposal: TradeProposal | None, caps) -> CapImpact:
        if proposal is None:
            return CapImpact()
        order_value = proposal.price_cents * proposal.size
        return CapImpact(
            order_value_cents=order_value,
            max_single_order_cents=caps.max_single_order_cents,
            max_market_exposure_cents=caps.max_market_exposure_cents,
            remaining_daily_loss_cents=max(0, caps.max_daily_loss_cents - state_module.STATE.daily_loss_cents),
            would_breach_single_order=order_value > caps.max_single_order_cents,
            would_breach_market_exposure=(
                self.exposure.market_exposure_cents(proposal.market_ticker) + order_value
                > caps.max_market_exposure_cents
            ),
            would_breach_daily_loss=state_module.STATE.daily_loss_cents >= caps.max_daily_loss_cents,
        )
