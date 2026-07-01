"""Proof-weighted aggression governor.

The governor consumes outputs from the mesh lanes and produces an
``AggressionAllocation`` decision.  It is intentionally not a static caution
rule; it prices risk using edge quality, forecast confidence, model agreement,
calibration support, market quality, cap impact, and mesh pressure terms.
"""

from __future__ import annotations

from typing import Any

from predator_mesh.aggression.models import AggressionAllocation, AggressionDecision
from predator_mesh.data_inflow.scoring import DataSourceScore, SourceTier
from predator_mesh.edge.models import EdgeCandidate
from strategies.governor import CapImpact, StrategyGovernorOutput


class ProofWeightedAggressionGovernor:
    """Convert mesh lane outputs into a risk-priced aggression allocation."""

    # Decision thresholds applied to the final allocation score.
    ATTACK_THRESHOLD = 0.75
    HOLD_THRESHOLD = 0.45
    REDUCE_THRESHOLD = 0.20

    # Risk terms are combined as multiplicative discounts so that several
    # moderate risks compound instead of one large risk swamping the score.
    MIN_FORECAST_CONFIDENCE = 0.30
    MIN_CALIBRATION_SUPPORT = 0.20
    DISAGREEMENT_REDUCE = 0.30
    DISAGREEMENT_NO_TRADE = 0.55
    LIQUIDITY_MIN = 0.25
    SPREAD_MIN = 0.25
    SETTLEMENT_RISK_HIGH = 0.70
    SETTLEMENT_RISK_CRITICAL = 0.85
    SOURCE_DECAY_HALF_LIFE = 0.25

    def allocate(
        self,
        edge_candidate: EdgeCandidate | None = None,
        source_scores: list[DataSourceScore] | None = None,
        forecast_confidence: float = 0.5,
        model_agreement: float = 1.0,
        calibration_support: float = 0.5,
        liquidity_score: float = 0.5,
        spread_score: float = 0.5,
        settlement_risk_score: float = 0.5,
        cap_impact: CapImpact | None = None,
        no_trade_pressure: float = 0.0,
        timeout_pressure: float = 0.0,
        source_decay: float = 0.0,
        governor_output: StrategyGovernorOutput | None = None,
    ) -> AggressionAllocation:
        """Price risk and return an ``AggressionAllocation``.

        All numeric inputs are clamped to unit intervals.  The allocation is
        deterministic and testable with no live calls.
        """
        cap_impact = cap_impact or CapImpact()

        blocked_by: list[str] = []
        reasoning_parts: list[str] = []

        # Hard blocks first: governor hard block or cap breach.
        if governor_output is not None and governor_output.decision.value == "NO_TRADE":
            blocked_by.extend(governor_output.blocked_by or ["governor_no_trade"])
            reasoning_parts.append(f"governor blocked: {governor_output.reason}")

        if (
            cap_impact.would_breach_single_order
            or cap_impact.would_breach_market_exposure
            or cap_impact.would_breach_daily_loss
        ):
            blocked_by.append("cap_breach")
            reasoning_parts.append("cap impact would breach configured limits")

        if blocked_by:
            return AggressionAllocation(
                decision=AggressionDecision.PASS,
                size_pct=0.0,
                confidence=self._clamp(forecast_confidence),
                reasoning="; ".join(reasoning_parts),
                blocked_by=blocked_by,
                meta=self._build_meta(
                    edge_candidate=edge_candidate,
                    source_scores=source_scores,
                    forecast_confidence=forecast_confidence,
                    model_agreement=model_agreement,
                    calibration_support=calibration_support,
                    liquidity_score=liquidity_score,
                    spread_score=spread_score,
                    settlement_risk_score=settlement_risk_score,
                    cap_impact=cap_impact,
                    no_trade_pressure=no_trade_pressure,
                    timeout_pressure=timeout_pressure,
                    source_decay=source_decay,
                    governor_output=governor_output,
                ),
            )

        # Base allocation from edge candidate quality.
        base_allocation = 0.5
        if edge_candidate is not None:
            base_allocation = edge_candidate.score.composite
            reasoning_parts.append(
                f"edge composite={edge_candidate.score.composite:.3f}"
            )
        else:
            reasoning_parts.append("no edge candidate; using default 0.5")

        # Forecast confidence and calibration support bound the upside.
        forecast_confidence = self._clamp(forecast_confidence)
        calibration_support = self._clamp(calibration_support)

        if forecast_confidence < self.MIN_FORECAST_CONFIDENCE:
            blocked_by.append("low_forecast_confidence")
            reasoning_parts.append(
                f"forecast confidence {forecast_confidence:.3f} below minimum"
            )

        if calibration_support < self.MIN_CALIBRATION_SUPPORT:
            blocked_by.append("low_calibration_support")
            reasoning_parts.append(
                f"calibration support {calibration_support:.3f} below minimum"
            )

        score = base_allocation * forecast_confidence * calibration_support

        # Model agreement / disagreement discount.
        agreement = self._clamp(model_agreement)
        disagreement = 1.0 - agreement
        if disagreement > self.DISAGREEMENT_NO_TRADE:
            blocked_by.append("extreme_model_disagreement")
            reasoning_parts.append(
                f"model disagreement {disagreement:.3f} above no-trade threshold"
            )
        elif disagreement > self.DISAGREEMENT_REDUCE:
            score *= 1.0 - (disagreement - self.DISAGREEMENT_REDUCE)
            reasoning_parts.append(f"model disagreement reduces allocation: {disagreement:.3f}")
        else:
            reasoning_parts.append(f"model agreement {agreement:.3f}")

        # Market quality discount.
        liquidity_score = self._clamp(liquidity_score)
        spread_score = self._clamp(spread_score)
        if liquidity_score < self.LIQUIDITY_MIN:
            blocked_by.append("poor_liquidity")
            reasoning_parts.append(f"liquidity {liquidity_score:.3f} too low")
        if spread_score < self.SPREAD_MIN:
            blocked_by.append("wide_spread")
            reasoning_parts.append(f"spread {spread_score:.3f} too wide")

        market_quality = min(liquidity_score, spread_score)
        score *= market_quality

        # Settlement risk discount.
        settlement_risk_score = self._clamp(settlement_risk_score)
        if settlement_risk_score > self.SETTLEMENT_RISK_CRITICAL:
            blocked_by.append("critical_settlement_risk")
            reasoning_parts.append(
                f"settlement risk {settlement_risk_score:.3f} critical"
            )
        elif settlement_risk_score > self.SETTLEMENT_RISK_HIGH:
            score *= 1.0 - (settlement_risk_score - self.SETTLEMENT_RISK_HIGH)
            reasoning_parts.append(
                f"settlement risk {settlement_risk_score:.3f} elevated"
            )
        else:
            score *= 1.0 - settlement_risk_score

        # Source scores: require at least one promoted source to attack.
        source_quality = self._source_quality(source_scores)
        score *= source_quality
        if source_scores:
            reasoning_parts.append(
                f"source quality {source_quality:.3f} from {len(source_scores)} sources"
            )

        # Pressure terms.
        no_trade_pressure = self._clamp(no_trade_pressure)
        timeout_pressure = self._clamp(timeout_pressure)
        source_decay = self._clamp(source_decay)

        pressure = max(no_trade_pressure, timeout_pressure)
        score *= 1.0 - pressure
        if pressure > 0.0:
            reasoning_parts.append(f"pressure discount {pressure:.3f}")

        discount = 0.5 ** (source_decay / self.SOURCE_DECAY_HALF_LIFE)
        score *= self._clamp(discount)
        if source_decay > 0.0:
            reasoning_parts.append(f"source decay {source_decay:.3f}")

        # Final confidence is the geometric mean of the strongest positive signals.
        confidence = (forecast_confidence * calibration_support * market_quality) ** (1.0 / 3.0)

        if blocked_by:
            return AggressionAllocation(
                decision=AggressionDecision.PASS,
                size_pct=0.0,
                confidence=self._clamp(confidence),
                reasoning="; ".join(reasoning_parts),
                blocked_by=blocked_by,
                meta=self._build_meta(
                    edge_candidate=edge_candidate,
                    source_scores=source_scores,
                    forecast_confidence=forecast_confidence,
                    model_agreement=model_agreement,
                    calibration_support=calibration_support,
                    liquidity_score=liquidity_score,
                    spread_score=spread_score,
                    settlement_risk_score=settlement_risk_score,
                    cap_impact=cap_impact,
                    no_trade_pressure=no_trade_pressure,
                    timeout_pressure=timeout_pressure,
                    source_decay=source_decay,
                    governor_output=governor_output,
                ),
            )

        size = self._clamp(score)
        decision = self._decide(size, governor_output)

        if decision == AggressionDecision.ESCALATE:
            reasoning_parts.append("escalated to operator review")
        elif decision == AggressionDecision.ATTACK:
            reasoning_parts.append("attacking with full risk-priced size")
        elif decision == AggressionDecision.HOLD:
            reasoning_parts.append("holding at reduced size")
        elif decision == AggressionDecision.REDUCE:
            reasoning_parts.append("reducing exposure")
        else:
            reasoning_parts.append("passing")

        return AggressionAllocation(
            decision=decision,
            size_pct=size,
            confidence=self._clamp(confidence),
            reasoning="; ".join(reasoning_parts),
            blocked_by=blocked_by,
            meta=self._build_meta(
                edge_candidate=edge_candidate,
                source_scores=source_scores,
                forecast_confidence=forecast_confidence,
                model_agreement=model_agreement,
                calibration_support=calibration_support,
                liquidity_score=liquidity_score,
                spread_score=spread_score,
                settlement_risk_score=settlement_risk_score,
                cap_impact=cap_impact,
                no_trade_pressure=no_trade_pressure,
                timeout_pressure=timeout_pressure,
                source_decay=source_decay,
                governor_output=governor_output,
            ),
        )

    def _decide(
        self,
        size: float,
        governor_output: StrategyGovernorOutput | None,
    ) -> AggressionDecision:
        """Map a continuous size to a discrete decision."""
        if governor_output is not None and governor_output.decision.value in {
            "REQUIRE_OPERATOR_REVIEW",
            "REQUIRE_MINIMAX_REVIEW",
        }:
            return AggressionDecision.ESCALATE
        if size >= self.ATTACK_THRESHOLD:
            return AggressionDecision.ATTACK
        if size >= self.HOLD_THRESHOLD:
            return AggressionDecision.HOLD
        if size >= self.REDUCE_THRESHOLD:
            return AggressionDecision.REDUCE
        return AggressionDecision.PASS

    def _source_quality(self, source_scores: list[DataSourceScore] | None) -> float:
        """Return a quality multiplier derived from source scores.

        Promoted sources boost quality; pruned sources collapse it.  No sources
        is treated as neutral (1.0) so the governor can still operate on edge
        and forecast inputs alone.
        """
        if not source_scores:
            return 1.0
        promoted = sum(1 for s in source_scores if s.tier is SourceTier.PROMOTE)
        pruned = sum(1 for s in source_scores if s.tier is SourceTier.PRUNE)
        total = len(source_scores)
        if pruned > 0 and promoted == 0:
            return 0.0
        if promoted > 0:
            return 0.8 + 0.2 * (promoted / total)
        return 0.9

    def _clamp(self, value: float) -> float:
        return float(max(0.0, min(1.0, value)))

    def _build_meta(
        self,
        edge_candidate: EdgeCandidate | None,
        source_scores: list[DataSourceScore] | None,
        forecast_confidence: float,
        model_agreement: float,
        calibration_support: float,
        liquidity_score: float,
        spread_score: float,
        settlement_risk_score: float,
        cap_impact: CapImpact,
        no_trade_pressure: float,
        timeout_pressure: float,
        source_decay: float,
        governor_output: StrategyGovernorOutput | None,
    ) -> dict[str, Any]:
        """Return a lightweight, deterministic meta dict for debugging."""
        return {
            "edge_candidate_id": edge_candidate.candidate_id if edge_candidate else None,
            "source_count": len(source_scores) if source_scores else 0,
            "forecast_confidence": round(self._clamp(forecast_confidence), 6),
            "model_agreement": round(self._clamp(model_agreement), 6),
            "calibration_support": round(self._clamp(calibration_support), 6),
            "liquidity_score": round(self._clamp(liquidity_score), 6),
            "spread_score": round(self._clamp(spread_score), 6),
            "settlement_risk_score": round(self._clamp(settlement_risk_score), 6),
            "cap_breach": bool(
                cap_impact.would_breach_single_order
                or cap_impact.would_breach_market_exposure
                or cap_impact.would_breach_daily_loss
            ),
            "no_trade_pressure": round(self._clamp(no_trade_pressure), 6),
            "timeout_pressure": round(self._clamp(timeout_pressure), 6),
            "source_decay": round(self._clamp(source_decay), 6),
            "governor_decision": governor_output.decision.value if governor_output else None,
        }
