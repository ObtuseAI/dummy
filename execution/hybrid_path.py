from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from execution.autonomous_path import AutonomousExecutionPath
from forecasting.hybrid_engine import HybridForecastEngine
from forecasting.model_influence_attestation import build_model_influence_attestation
from forecasting.model_probability_authority import (
    ModelProbabilityAuthorityDecision,
    is_sports_model_market,
)
from forecasting.real_market_loop import (
    MODEL_MODE_DEGRADED_QUANT_ONLY,
    MODEL_MODE_LIVE_HYBRID,
    MODEL_MODE_MOCK_ONLY,
    RealMarketForecastLoopV2,
)
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
from autonomy.target_policy import (
    has_prediction_target_authority,
    is_data_only_target,
    is_equity_index_target,
    is_prediction_quarantined_target,
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
        self.model_authority_decisions = {}
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
                scored_mock = []
                for market, contract, book in mock_entries:
                    scores = self._score_market(market, contract, book)
                    if scores is not None:
                        scored_mock.append((market, contract, book, scores))
                entries = self._select_from_scored(
                    scored_mock,
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
                    scored_mock = []
                    for market, contract, book in mock_entries:
                        scores = self._score_market(market, contract, book)
                        if scores is not None:
                            scored_mock.append((market, contract, book, scores))
                    entries = self._select_from_scored(
                        scored_mock,
                        max_markets,
                    )
        finally:
            if reader is not None:
                await reader.close()

        # Never spend model budget on deterministic mock fallback entries.
        # The source check later also blocks firewall progression, but this
        # earlier gate is what prevents the paid requests themselves.
        if snapshot_source != "live" and self.model_mode == MODEL_MODE_LIVE_HYBRID:
            self.model_mode = MODEL_MODE_DEGRADED_QUANT_ONLY
            self.model_degradation_reasons = sorted(
                set(self.model_degradation_reasons + ["non_live_market_data"])
            )

        for market, contract, orderbook, scores in entries:
            if contract.ticker != contract_ticker:
                continue
            if is_prediction_quarantined_target(
                market.ticker,
                category=getattr(market, "category", None),
            ) or is_prediction_quarantined_target(
                contract.ticker,
                category=getattr(market, "category", None),
            ):
                continue
            base = self._build_base_forecast(market, contract, orderbook, scores)
            raw_review = None
            failures: list[str] = []
            if self.model_mode == MODEL_MODE_LIVE_HYBRID:
                try:
                    raw_review = await self.hybrid_engine.hybrid_review(
                        base=base,
                        orderbook=orderbook,
                        market=market,
                        contract=contract,
                        scores=scores,
                        model_mode=self.model_mode,
                    )
                except Exception as exc:
                    failures.append(f"review_exception:{type(exc).__name__}")
                failures.extend(self._review_contract_failures(raw_review))
                if failures:
                    self.model_mode = MODEL_MODE_DEGRADED_QUANT_ONLY
                    self.model_degradation_reasons = sorted(
                        set(self.model_degradation_reasons + failures)
                    )
                    raw_review = None
            reason = (
                "live_model_calls_disabled"
                if self.model_mode == MODEL_MODE_MOCK_ONLY
                else "hybrid_model_validation_failed"
            )
            review = self._complete_review_set(raw_review, base, reason)
            opinion = self._synthesize_opinion(base, scores, review)
            authority_summary = self._model_authority_summary()
            authority_decision = next(
                iter(self.model_authority_decisions.values()),
                None,
            )
            return {
                "source": snapshot_source,
                "model_mode": self.model_mode,
                **authority_summary,
                "model_degradation_reasons": self.model_degradation_reasons,
                "credentials_present": self.credentials_present,
                "market": market,
                "contract": contract,
                "orderbook": orderbook,
                "scores": scores,
                "base_forecast": base,
                "review": review,
                "opinion": opinion,
                "model_probability_authority_decision": authority_decision,
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

        if is_data_only_target(market_ticker) or is_data_only_target(contract_ticker):
            payload = {
                **base_payload,
                "status": "blocked",
                "rejected_by": "data_only_target",
                "reason": "Weather and commodity contracts are contextual data only",
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}
        if is_equity_index_target(market_ticker) or is_equity_index_target(
            contract_ticker
        ):
            payload = {
                **base_payload,
                "status": "blocked",
                "rejected_by": "equity_index_target_quarantine",
                "reason": "Target is outside Dummy's supported prediction surface",
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

        if details.get("source") != "live":
            payload = {
                **base_payload,
                "status": "no_trade",
                "source": details.get("source", "unknown"),
                "model_mode": details.get("model_mode", "unknown"),
                "credentials_present": details.get("credentials_present", False),
                "rejected_by": "market_data_source",
                "reason": "Non-live market data cannot advance to the live firewall",
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "no_trade", payload)
            return {**payload, "proof_reference": proof_ref}
        if details.get("model_mode") != MODEL_MODE_LIVE_HYBRID:
            payload = {
                **base_payload,
                "status": "no_trade",
                "source": details.get("source", "unknown"),
                "model_mode": details.get("model_mode", "unknown"),
                "model_degradation_reasons": details.get(
                    "model_degradation_reasons", []
                ),
                "credentials_present": details.get("credentials_present", False),
                "rejected_by": "hybrid_model_validation",
                "reason": "Only a fully validated LIVE_HYBRID review may advance through this hybrid rehearsal path",
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "no_trade", payload)
            return {**payload, "proof_reference": proof_ref}

        opinion: ForecastOpinion = details["opinion"]
        orderbook: OrderBook = details["orderbook"]
        base_forecast: Forecast = details["base_forecast"]
        review: dict[str, Any] = details["review"]
        scores = details.get("scores") or {}
        market = details.get("market")
        contract = details.get("contract")
        identity_mismatches: list[str] = []
        if str(getattr(market, "ticker", "")) != market_ticker:
            identity_mismatches.append("market")
        if str(getattr(contract, "ticker", "")) != contract_ticker:
            identity_mismatches.append("contract")
        for label, candidate in (
            ("orderbook", orderbook),
            ("forecast", base_forecast),
            ("opinion", opinion),
        ):
            if (
                str(getattr(candidate, "market_ticker", "")) != market_ticker
                or str(getattr(candidate, "contract_ticker", ""))
                != contract_ticker
            ):
                identity_mismatches.append(label)
        if identity_mismatches:
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "context_integrity",
                "reason": "Hybrid market, forecast, or orderbook identity mismatch",
                "identity_mismatches": sorted(set(identity_mismatches)),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}

        market_category = str(getattr(market, "category", ""))
        if is_prediction_quarantined_target(
            market_ticker,
            category=market_category,
        ) or is_prediction_quarantined_target(
            contract_ticker,
            category=market_category,
        ):
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "prediction_target_quarantine",
                "reason": (
                    "Verified market category has zero prediction and proposal "
                    "authority under the shared target policy"
                ),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}
        if not (
            has_prediction_target_authority(
                market_ticker,
                category=market_category,
            )
            and has_prediction_target_authority(
                contract_ticker,
                category=market_category,
            )
        ):
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "prediction_target_authority",
                "reason": (
                    "Structured live-market context does not establish "
                    "prediction-target authority"
                ),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}
        live_phase = scores.get("live_phase")
        if (
            is_sports_model_market(
                ticker=contract_ticker,
                category=market_category,
            )
            and live_phase is not True
            and live_phase is not False
        ):
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "sports_phase_authority",
                "reason": (
                    "Sports phase is unknown or ambiguous; no model probability "
                    "or order authority is available"
                ),
                "model_probability_authority": Decimal("0"),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}
        model_probability_authority = Decimal(
            str(details.get("model_probability_authority") or 0)
        )
        model_operationally_authorized = model_probability_authority > 0
        authority_decision = details.get("model_probability_authority_decision")
        if model_operationally_authorized and not (
            isinstance(authority_decision, ModelProbabilityAuthorityDecision)
            and authority_decision.authorized
            and authority_decision.weight == model_probability_authority
        ):
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "model_probability_authority_attestation",
                "reason": (
                    "Operational model probability lacks its exact typed "
                    "authority decision"
                ),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}

        # A validated panel may abstain, but that abstention is operational only
        # after the exact market scope has earned model authority.  Revalidate
        # the complete review contract at this handoff so stale mock/fallback
        # text cannot become a veto merely because a caller mislabeled the mode.
        panel_no_trade_reason = self._authorized_panel_no_trade_reason(
            opinion=opinion,
            review=review,
            model_operationally_authorized=model_operationally_authorized,
        )
        if panel_no_trade_reason is not None:
            no_trade = NoTradeReason(
                market_ticker=market_ticker,
                contract_ticker=contract_ticker,
                reason=panel_no_trade_reason,
                contributing_factors=[
                    "validated_hybrid_panel_no_trade",
                    "model_probability_scope_authorized",
                ],
                model_summary=opinion.model_summary,
                timestamp=datetime.now(timezone.utc),
                proof_reference=opinion.proof_reference,
            )
            payload = {
                **base_payload,
                "status": "no_trade",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "authorized_panel_no_trade",
                "reason": panel_no_trade_reason,
                "model_probability_authority": model_probability_authority,
                "forecast_opinion": opinion.model_dump(),
                "strategy_governor_decision": "NOT_EVALUATED_PANEL_VETO",
                "no_trade_reason": no_trade.model_dump(),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "no_trade", payload)
            return {**payload, "proof_reference": proof_ref}

        # The hybrid model review may revise the base forecast.  Reflect the
        # reviewed opinion in the forecast used by the firewall so the edge gate
        # is evaluated against the model consensus rather than the raw mid.
        base_forecast.market_implied_probability = opinion.market_implied_probability
        base_forecast.dummy_probability = opinion.dummy_probability
        base_forecast.probability_delta = opinion.probability_delta
        base_forecast.expected_edge = opinion.probability_delta
        base_forecast.edge_after_fees = max(Decimal("0"), opinion.probability_delta - Decimal("0.005"))
        base_forecast.confidence_score = opinion.confidence_score

        if model_operationally_authorized:
            intelligence_results = await self.intelligence.evaluate(
                base_forecast,
                orderbook,
                market_category=market_category,
            )
        else:
            intelligence_results = self.intelligence.evaluate_quant_only(
                base_forecast,
                orderbook,
                market_category=market_category,
            )
        selected = self._select_intelligence_result(intelligence_results, strategy_name)

        scanner = getattr(self.intelligence, "scanner", None)
        family_authority = getattr(scanner, "family_has_prediction_authority", None)
        selected_scan = getattr(selected, "scan_result", None)
        selected_family = str(getattr(selected_scan, "family", ""))
        if not (
            selected_scan is not None
            and callable(family_authority)
            and family_authority(selected_family) is True
        ):
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "strategy_prediction_authority",
                "reason": "Selected strategy lacks explicit prediction authority",
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}

        selected_proposal = selected_scan.proposal
        selection_identity_mismatch = (
            selected_scan.market_ticker != market_ticker
            or selected_scan.contract_ticker != contract_ticker
            or (
                selected_proposal is not None
                and (
                    selected_proposal.market_ticker != market_ticker
                    or selected_proposal.contract_ticker != contract_ticker
                )
            )
        )
        selected_target_quarantined = selected_proposal is not None and (
            is_prediction_quarantined_target(
                selected_proposal.market_ticker,
                category=market_category,
            )
            or is_prediction_quarantined_target(
                selected_proposal.contract_ticker,
                category=market_category,
            )
        )
        if selection_identity_mismatch or selected_target_quarantined:
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": (
                    "prediction_target_quarantine"
                    if selected_target_quarantined
                    else "context_integrity"
                ),
                "reason": (
                    "Selected proposal violates target policy"
                    if selected_target_quarantined
                    else "Selected strategy/proposal identity does not match the forecast"
                ),
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}

        # On the zero-authority path, evaluate_quant_only supplies a neutral,
        # deterministic critique. It is not model output and cannot change the
        # quantitative scan; it simply avoids treating "model excluded" as an
        # operator-warning verdict.
        strategy_critique = selected.critique if selected else None
        risk_critique = (
            self._risk_critique_from_review(review)
            if model_operationally_authorized
            else None
        )

        # The first panel review was already route/schema validated.  Do not
        # make a second, independently unvalidated model call here.  Until the
        # exact scope earns authority, even the validated model disagreement is
        # report-only and excluded from governor inputs.
        if model_operationally_authorized:
            disagreement_score = max(
                Decimal("0"), min(Decimal("1"), opinion.model_disagreement)
            )
            disagreement = {
                "disagreement_score": disagreement_score,
                "source_of_disagreement": "validated_hybrid_panel",
                "required_action": self.disagreement._required_action(disagreement_score),
                "no_trade_bias_adjustment": self.disagreement._bias_adjustment(disagreement_score),
                "proof_reference": opinion.proof_reference,
                "model_probability_authority": model_probability_authority,
                "operationally_authorized": True,
            }
        else:
            disagreement = {
                "disagreement_score": Decimal("0"),
                "source_of_disagreement": "model_research_excluded",
                "required_action": "NONE_RESEARCH_ONLY",
                "no_trade_bias_adjustment": Decimal("0"),
                "proof_reference": opinion.proof_reference,
                "model_probability_authority": Decimal("0"),
                "operationally_authorized": False,
            }

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
            market_category=market_category,
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

        if (
            proposal.market_ticker != market_ticker
            or proposal.contract_ticker != contract_ticker
            or base_forecast.market_ticker != proposal.market_ticker
            or base_forecast.contract_ticker != proposal.contract_ticker
            or orderbook.market_ticker != proposal.market_ticker
            or orderbook.contract_ticker != proposal.contract_ticker
        ):
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "context_integrity",
                "reason": "Final proposal identity does not match forecast and orderbook",
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
            return {**payload, "proof_reference": proof_ref}
        if not (
            has_prediction_target_authority(
                proposal.market_ticker,
                category=market_category,
            )
            and has_prediction_target_authority(
                proposal.contract_ticker,
                category=market_category,
            )
        ):
            payload = {
                **base_payload,
                "status": "blocked",
                "source": details["source"],
                "model_mode": details["model_mode"],
                "credentials_present": details["credentials_present"],
                "rejected_by": "prediction_target_authority",
                "reason": "Final proposal lacks verified prediction-target authority",
                "live_submitted": False,
            }
            proof_ref = write_proof("rehearse_live_cap_v2", "blocked", payload)
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

        request_fields = {
            "proposal_id": proposal.id,
            "market_ticker": proposal.market_ticker,
            "contract_ticker": proposal.contract_ticker,
            "side": proposal.side,
            "price_cents": proposal.price_cents,
            "size": proposal.size,
            "strategy_proof_reference": proposal.proof_reference,
            # The request is bound to the exact Forecast object evaluated by
            # the firewall; the LLM opinion proof remains supporting evidence.
            "forecast_proof_reference": base_forecast.proof_reference,
            "adapter_name": self.adapter_name,
        }
        request = LiveOrderRequest(
            **request_fields,
            model_influence_attestation=build_model_influence_attestation(
                base_forecast,
                request_fields,
                authority_decision=authority_decision,
                market_category=market_category,
                live_phase=live_phase,
                supporting_model_output_reference=opinion.proof_reference,
            ),
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

    def _authorized_panel_no_trade_reason(
        self,
        *,
        opinion: ForecastOpinion,
        review: dict[str, Any],
        model_operationally_authorized: bool,
    ) -> str | None:
        """Return a hard-veto reason only for an authorized, valid panel."""
        if not model_operationally_authorized:
            return None
        if self.loop._review_contract_failures(review):
            return None
        reason = opinion.no_trade_reason
        if not isinstance(reason, str):
            return None
        normalized = reason.strip()
        return normalized or None

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
            # Rehearsal proposals are passive maker limits. Crossing the ask
            # would be a taker order and must be modeled by the separate
            # executable-depth path instead of mislabeled here.
            price = orderbook.bids[-1].price if orderbook.bids else 50
        else:
            price = 100 - (orderbook.asks[0].price if orderbook.asks else 50)
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
