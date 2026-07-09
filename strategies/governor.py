from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from core.ontology import ComplianceVerdict, ForecastOpinion, HybridReviewResult, StrategyCritique


class GovernorDecision(str, Enum):
    APPROVE_FOR_FIREWALL_REHEARSAL = "APPROVE_FOR_FIREWALL_REHEARSAL"
    NO_TRADE = "NO_TRADE"
    REQUIRE_MORE_EVIDENCE = "REQUIRE_MORE_EVIDENCE"
    REQUIRE_MINIMAX_REVIEW = "REQUIRE_MINIMAX_REVIEW"
    REQUIRE_OPERATOR_REVIEW = "REQUIRE_OPERATOR_REVIEW"
    QUARANTINE_STRATEGY = "QUARANTINE_STRATEGY"


@dataclass
class RiskCritique:
    """Lightweight risk critique consumed by the strategy governor.

    This mirrors the ``RISK_CRITIQUE`` model task output without expanding
    ``core.ontology`` for a single V8 workstream.
    """

    verdict: str = "warn"  # proceed / warn / block
    risk_level: str = "medium"  # low / medium / high / critical
    reasoning: str = ""
    proof_reference: str = ""


@dataclass
class MarketQualityScores:
    """Numeric quality dimensions extracted from a market snapshot."""

    liquidity_score: float = 0.0
    spread_score: float = 0.0
    freshness_score: float = 0.0
    depth_score: float = 0.0
    settlement_risk_score: float = 0.0

    @classmethod
    def from_opinion(cls, opinion: ForecastOpinion) -> "MarketQualityScores":
        """Best-effort parse quality scores from opinion calibration notes."""
        values: dict[str, float] = {}
        for note in opinion.calibration_notes or []:
            if "=" in note:
                key, _, raw = note.partition("=")
                try:
                    values[key.strip()] = float(raw.strip())
                except ValueError:
                    continue
        return cls(
            liquidity_score=values.get("liquidity_score", 0.0),
            spread_score=values.get("spread_score", 0.0),
            freshness_score=values.get("freshness_score", 0.0),
            depth_score=values.get("depth_score", 0.0),
            settlement_risk_score=values.get("settlement_risk_score", 0.0),
        )


@dataclass
class CapImpact:
    """Estimated impact of a prospective trade against caps."""

    order_value_cents: int = 0
    max_single_order_cents: int = 100
    max_market_exposure_cents: int = 500
    remaining_daily_loss_cents: int = 500
    would_breach_single_order: bool = False
    would_breach_market_exposure: bool = False
    would_breach_daily_loss: bool = False


@dataclass
class StrategyGovernorOutput:
    decision: GovernorDecision
    reason: str
    no_trade_bias: float = 0.0
    blocked_by: list[str] = field(default_factory=list)
    proof_reference: str = ""


class StrategyGovernor:
    """Gatekeeper between strategy intelligence and firewall rehearsal.

    The governor is intentionally conservative: any hard blocker yields
    ``NO_TRADE``; ambiguous conditions escalate to review or evidence
    gathering rather than proceeding to rehearsal.
    """

    # Thresholds tuned for prediction-market micro-caps.
    LIQUIDITY_MIN = 0.30
    SPREAD_MIN = 0.30  # spread_score below this implies a wide spread
    FRESHNESS_MIN = 0.30
    SETTLEMENT_RISK_HIGH = 0.70
    SETTLEMENT_RISK_CRITICAL = 0.85
    DISAGREEMENT_REVIEW = 0.30
    DISAGREEMENT_NO_TRADE = 0.50
    CALIBRATION_CONFIDENCE_MIN = 0.30

    def evaluate(
        self,
        opinion: ForecastOpinion,
        strategy_critique: StrategyCritique | None = None,
        risk_critique: RiskCritique | None = None,
        hybrid_review: HybridReviewResult | None = None,
        quality_scores: MarketQualityScores | None = None,
        calibration_confidence: float = 0.5,
        disagreement_score: float = 0.0,
        cap_impact: CapImpact | None = None,
        compliance_verdict: ComplianceVerdict | None = None,
        model_output_firewall_blocked: bool = False,
    ) -> StrategyGovernorOutput:
        if quality_scores is None:
            quality_scores = MarketQualityScores.from_opinion(opinion)
        if cap_impact is None:
            cap_impact = CapImpact()
        if compliance_verdict is None:
            compliance_verdict = ComplianceVerdict(passed=True, blocked_categories=[], reason="")
        if risk_critique is None:
            risk_critique = RiskCritique()
        if strategy_critique is None:
            strategy_critique = StrategyCritique(
                strategy_family="unknown",
                market_ticker=opinion.market_ticker,
                contract_ticker=opinion.contract_ticker,
                verdict="warn",
                edge_assessment="",
                risk_assessment="",
                reasoning="",
                timestamp=datetime.now(timezone.utc),
                proof_reference="default_strategy_critique",
            )

        blocked_by: list[str] = []
        no_trade_bias = float(min(1.0, disagreement_score))

        # Hard blocks first.
        if model_output_firewall_blocked:
            blocked_by.append("model_output_firewall_block")
            return self._output(
                GovernorDecision.NO_TRADE,
                "Model output firewall block converted to NO_TRADE",
                blocked_by,
                no_trade_bias,
            )

        if not compliance_verdict.passed:
            blocked_by.append("compliance_block")
            return self._output(
                GovernorDecision.NO_TRADE,
                f"Compliance block: {compliance_verdict.reason}",
                blocked_by,
                no_trade_bias,
            )

        if quality_scores.liquidity_score < self.LIQUIDITY_MIN:
            blocked_by.append("poor_liquidity")
            return self._output(
                GovernorDecision.NO_TRADE,
                f"Poor liquidity (score={quality_scores.liquidity_score:.4f})",
                blocked_by,
                no_trade_bias,
            )

        if quality_scores.spread_score < self.SPREAD_MIN:
            blocked_by.append("wide_spread")
            return self._output(
                GovernorDecision.NO_TRADE,
                f"Wide spread (spread_score={quality_scores.spread_score:.4f})",
                blocked_by,
                no_trade_bias,
            )

        if quality_scores.freshness_score < self.FRESHNESS_MIN:
            blocked_by.append("stale_data")
            return self._output(
                GovernorDecision.NO_TRADE,
                f"Stale data (freshness_score={quality_scores.freshness_score:.4f})",
                blocked_by,
                no_trade_bias,
            )

        if not opinion.proof_reference or not strategy_critique.proof_reference:
            blocked_by.append("missing_proof")
            return self._output(
                GovernorDecision.REQUIRE_MORE_EVIDENCE,
                "Missing proof reference; more evidence required",
                blocked_by,
                no_trade_bias,
            )

        if cap_impact.would_breach_single_order or cap_impact.would_breach_market_exposure or cap_impact.would_breach_daily_loss:
            blocked_by.append("cap_breach")
            return self._output(
                GovernorDecision.NO_TRADE,
                "Cap impact would breach configured limits",
                blocked_by,
                no_trade_bias,
            )

        # Strategy and risk critique blocks.
        if strategy_critique.verdict.lower() == "block":
            blocked_by.append("strategy_critique_block")
            return self._output(
                GovernorDecision.NO_TRADE,
                f"Strategy critique blocked: {strategy_critique.reasoning}",
                blocked_by,
                no_trade_bias,
            )

        if risk_critique.verdict.lower() == "block" or risk_critique.risk_level.lower() in ("high", "critical"):
            blocked_by.append("high_risk")
            if risk_critique.risk_level.lower() == "critical":
                return self._output(
                    GovernorDecision.NO_TRADE,
                    f"Critical settlement/risk: {risk_critique.reasoning}",
                    blocked_by,
                    no_trade_bias,
                )
            return self._output(
                GovernorDecision.REQUIRE_OPERATOR_REVIEW,
                f"High settlement risk: {risk_critique.reasoning}",
                blocked_by,
                no_trade_bias,
            )

        if quality_scores.settlement_risk_score > self.SETTLEMENT_RISK_CRITICAL:
            blocked_by.append("critical_settlement_risk")
            return self._output(
                GovernorDecision.NO_TRADE,
                f"Critical settlement risk (score={quality_scores.settlement_risk_score:.4f})",
                blocked_by,
                no_trade_bias,
            )

        if quality_scores.settlement_risk_score > self.SETTLEMENT_RISK_HIGH:
            blocked_by.append("high_settlement_risk")
            return self._output(
                GovernorDecision.REQUIRE_OPERATOR_REVIEW,
                f"High settlement risk (score={quality_scores.settlement_risk_score:.4f})",
                blocked_by,
                no_trade_bias,
            )

        # Calibration and model disagreement gates.
        if calibration_confidence < self.CALIBRATION_CONFIDENCE_MIN:
            blocked_by.append("low_calibration_confidence")
            return self._output(
                GovernorDecision.REQUIRE_MORE_EVIDENCE,
                f"Low calibration confidence ({calibration_confidence:.4f})",
                blocked_by,
                no_trade_bias,
            )

        if disagreement_score > self.DISAGREEMENT_NO_TRADE:
            blocked_by.append("extreme_disagreement")
            return self._output(
                GovernorDecision.NO_TRADE,
                f"Extreme model disagreement (score={disagreement_score:.4f})",
                blocked_by,
                no_trade_bias,
            )

        if disagreement_score > self.DISAGREEMENT_REVIEW:
            blocked_by.append("high_disagreement")
            return self._output(
                GovernorDecision.REQUIRE_MINIMAX_REVIEW,
                f"High model disagreement (score={disagreement_score:.4f}); minimax review required",
                blocked_by,
                no_trade_bias,
            )

        # Hybrid review conflicts.
        if hybrid_review is not None and hybrid_review.verdict.lower() in ("disagree", "conflict"):
            blocked_by.append("hybrid_review_conflict")
            return self._output(
                GovernorDecision.REQUIRE_MINIMAX_REVIEW,
                "Hybrid review disagreement detected",
                blocked_by,
                no_trade_bias,
            )

        # Soft warnings that still allow rehearsal if operator wants to be asked.
        if strategy_critique.verdict.lower() == "warn":
            return self._output(
                GovernorDecision.REQUIRE_OPERATOR_REVIEW,
                f"Strategy critique warning: {strategy_critique.reasoning}",
                blocked_by=["strategy_critique_warn"],
                no_trade_bias=no_trade_bias,
            )

        return self._output(
            GovernorDecision.APPROVE_FOR_FIREWALL_REHEARSAL,
            "Approved for firewall rehearsal",
            blocked_by,
            no_trade_bias,
        )

    def _output(
        self,
        decision: GovernorDecision,
        reason: str,
        blocked_by: list[str],
        no_trade_bias: float,
    ) -> StrategyGovernorOutput:
        return StrategyGovernorOutput(
            decision=decision,
            reason=reason,
            no_trade_bias=no_trade_bias,
            blocked_by=blocked_by,
            proof_reference=f"gov_{decision.value}_{uuid.uuid4()}",
        )


def _quality_scores_from_opinion(opinion: ForecastOpinion) -> MarketQualityScores:
    return MarketQualityScores.from_opinion(opinion)


def generate_strategy_governor_reports(
    artifact_dir: str | Path = "artifacts/dummy",
) -> dict[str, Path]:
    """Generate required V8 strategy governor artifacts.

    Uses deterministic synthetic inputs so the reports are reproducible in
    test environments without live credentials or market data.
    """
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    def make_opinion(
        market_ticker: str,
        contract_ticker: str,
        liquidity: float,
        spread: float,
        freshness: float,
        settlement_risk: float,
        confidence: float,
        no_trade_reason: str | None = None,
    ) -> ForecastOpinion:
        return ForecastOpinion(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            forecast_reference=f"forecast_{market_ticker}_{contract_ticker}",
            market_implied_probability=Decimal("0.5000"),
            dummy_probability=Decimal("0.5500"),
            probability_delta=Decimal("0.0500"),
            confidence_score=Decimal(str(confidence)),
            uncertainty_band=(Decimal("0.50"), Decimal("0.60")),
            model_summary="mock_governor_fixture",
            reasoning="synthetic fixture for governor report",
            no_trade_reason=no_trade_reason,
            calibration_notes=[
                f"liquidity_score={liquidity}",
                f"spread_score={spread}",
                f"freshness_score={freshness}",
                f"depth_score={freshness}",
                f"settlement_risk_score={settlement_risk}",
            ],
            timestamp=now,
            expiration=now,
            proof_reference=f"proof_{market_ticker}_{contract_ticker}",
        )

    governor = StrategyGovernor()

    fixtures = [
        {
            "name": "healthy_approve",
            "opinion": make_opinion("HEALTHY", "HEALTHY-YES", 0.80, 0.80, 0.95, 0.10, 0.80),
            "critique": StrategyCritique(
                strategy_family="probability_disagreement",
                market_ticker="HEALTHY",
                contract_ticker="HEALTHY-YES",
                verdict="proceed",
                edge_assessment="positive",
                risk_assessment="low",
                confidence_adjustment=Decimal("0.05"),
                reasoning="clean signal",
                timestamp=now,
                proof_reference="critique_healthy",
            ),
            "risk": RiskCritique(verdict="proceed", risk_level="low", reasoning="low risk", proof_reference="risk_healthy"),
            "disagreement": 0.05,
            "calibration_confidence": 0.75,
        },
        {
            "name": "poor_liquidity_block",
            "opinion": make_opinion("ILLIQ", "ILLIQ-YES", 0.10, 0.80, 0.95, 0.10, 0.80),
            "critique": None,
            "risk": None,
            "disagreement": 0.05,
            "calibration_confidence": 0.75,
        },
        {
            "name": "wide_spread_block",
            "opinion": make_opinion("WIDESPREAD", "WIDESPREAD-YES", 0.80, 0.10, 0.95, 0.10, 0.80),
            "critique": None,
            "risk": None,
            "disagreement": 0.05,
            "calibration_confidence": 0.75,
        },
        {
            "name": "stale_data_block",
            "opinion": make_opinion("STALE", "STALE-YES", 0.80, 0.80, 0.10, 0.10, 0.80),
            "critique": None,
            "risk": None,
            "disagreement": 0.05,
            "calibration_confidence": 0.75,
        },
        {
            "name": "high_settlement_review",
            "opinion": make_opinion("SETTLE", "SETTLE-YES", 0.80, 0.80, 0.95, 0.75, 0.80),
            "critique": StrategyCritique(
                strategy_family="probability_disagreement",
                market_ticker="SETTLE",
                contract_ticker="SETTLE-YES",
                verdict="proceed",
                edge_assessment="positive",
                risk_assessment="elevated",
                confidence_adjustment=Decimal("0.0"),
                reasoning="elevated settlement risk",
                timestamp=now,
                proof_reference="critique_settle",
            ),
            "risk": RiskCritique(verdict="warn", risk_level="high", reasoning="settlement uncertain", proof_reference="risk_settle"),
            "disagreement": 0.10,
            "calibration_confidence": 0.75,
        },
        {
            "name": "high_disagreement_review",
            "opinion": make_opinion("DISAGREE", "DISAGREE-YES", 0.80, 0.80, 0.95, 0.10, 0.80),
            "critique": StrategyCritique(
                strategy_family="probability_disagreement",
                market_ticker="DISAGREE",
                contract_ticker="DISAGREE-YES",
                verdict="proceed",
                edge_assessment="positive",
                risk_assessment="low",
                confidence_adjustment=Decimal("0.0"),
                reasoning="models diverge",
                timestamp=now,
                proof_reference="critique_disagree",
            ),
            "risk": RiskCritique(verdict="proceed", risk_level="low", reasoning="low risk", proof_reference="risk_disagree"),
            "disagreement": 0.40,
            "calibration_confidence": 0.75,
        },
        {
            "name": "extreme_disagreement_block",
            "opinion": make_opinion("EXTREME", "EXTREME-YES", 0.80, 0.80, 0.95, 0.10, 0.80),
            "critique": StrategyCritique(
                strategy_family="probability_disagreement",
                market_ticker="EXTREME",
                contract_ticker="EXTREME-YES",
                verdict="proceed",
                edge_assessment="positive",
                risk_assessment="low",
                confidence_adjustment=Decimal("0.0"),
                reasoning="models strongly diverge",
                timestamp=now,
                proof_reference="critique_extreme",
            ),
            "risk": RiskCritique(verdict="proceed", risk_level="low", reasoning="low risk", proof_reference="risk_extreme"),
            "disagreement": 0.60,
            "calibration_confidence": 0.75,
        },
        {
            "name": "low_calibration_evidence",
            "opinion": make_opinion("LOWCAL", "LOWCAL-YES", 0.80, 0.80, 0.95, 0.10, 0.80),
            "critique": StrategyCritique(
                strategy_family="probability_disagreement",
                market_ticker="LOWCAL",
                contract_ticker="LOWCAL-YES",
                verdict="proceed",
                edge_assessment="positive",
                risk_assessment="low",
                confidence_adjustment=Decimal("0.0"),
                reasoning="thin calibration history",
                timestamp=now,
                proof_reference="critique_lowcal",
            ),
            "risk": RiskCritique(verdict="proceed", risk_level="low", reasoning="low risk", proof_reference="risk_lowcal"),
            "disagreement": 0.10,
            "calibration_confidence": 0.10,
        },
        {
            "name": "strategy_block",
            "opinion": make_opinion("BLOCKED", "BLOCKED-YES", 0.80, 0.80, 0.95, 0.10, 0.80),
            "critique": StrategyCritique(
                strategy_family="probability_disagreement",
                market_ticker="BLOCKED",
                contract_ticker="BLOCKED-YES",
                verdict="block",
                edge_assessment="negative",
                risk_assessment="high",
                confidence_adjustment=Decimal("-0.20"),
                reasoning="edge not justified",
                timestamp=now,
                proof_reference="critique_blocked",
            ),
            "risk": RiskCritique(verdict="proceed", risk_level="low", reasoning="low risk", proof_reference="risk_blocked"),
            "disagreement": 0.05,
            "calibration_confidence": 0.75,
        },
        {
            "name": "model_output_firewall_block",
            "opinion": make_opinion("FIREWALL", "FIREWALL-YES", 0.80, 0.80, 0.95, 0.10, 0.80),
            "critique": StrategyCritique(
                strategy_family="probability_disagreement",
                market_ticker="FIREWALL",
                contract_ticker="FIREWALL-YES",
                verdict="proceed",
                edge_assessment="positive",
                risk_assessment="low",
                confidence_adjustment=Decimal("0.0"),
                reasoning="clean signal",
                timestamp=now,
                proof_reference="critique_firewall",
            ),
            "risk": RiskCritique(verdict="proceed", risk_level="low", reasoning="low risk", proof_reference="risk_firewall"),
            "disagreement": 0.05,
            "calibration_confidence": 0.75,
            "model_output_firewall_blocked": True,
        },
    ]

    decisions: list[dict[str, Any]] = []
    for fixture in fixtures:
        opinion = fixture["opinion"]
        output = governor.evaluate(
            opinion=opinion,
            strategy_critique=fixture.get("critique"),
            risk_critique=fixture.get("risk"),
            quality_scores=_quality_scores_from_opinion(opinion),
            disagreement_score=fixture["disagreement"],
            calibration_confidence=fixture["calibration_confidence"],
            model_output_firewall_blocked=fixture.get("model_output_firewall_blocked", False),
        )
        decisions.append(
            {
                "fixture": fixture["name"],
                "market_ticker": opinion.market_ticker,
                "contract_ticker": opinion.contract_ticker,
                "decision": output.decision.value,
                "reason": output.reason,
                "blocked_by": output.blocked_by,
                "no_trade_bias": output.no_trade_bias,
                "proof_reference": output.proof_reference,
            }
        )

    report_path = artifact_path / "strategy_governor_report_v1.json"
    manifest_path = artifact_path / "strategy_governor_decision_manifest_v1.json"

    report = {
        "report_type": "strategy_governor_report_v1",
        "generated_at": now.isoformat(),
        "workstream": "V8: Strategy Governor",
        "decision_count": len(decisions),
        "decision_summary": {
            decision: sum(1 for d in decisions if d["decision"] == decision)
            for decision in sorted({d["decision"] for d in decisions})
        },
        "decisions": decisions,
        "verdict": "PASS",
    }
    report_path.write_text(json.dumps(report, indent=2))

    manifest = {
        "manifest_type": "strategy_governor_decision_manifest_v1",
        "generated_at": now.isoformat(),
        "workstream": "V8: Strategy Governor",
        "decision_count": len(decisions),
        "decisions": decisions,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return {"report": report_path, "manifest": manifest_path}
