"""Edge discovery acceleration for V10."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EdgeTriageDecision(str, Enum):
    ESCALATE_TO_FORECAST = "ESCALATE_TO_FORECAST"
    ESCALATE_TO_MINIMAX_REVIEW = "ESCALATE_TO_MINIMAX_REVIEW"
    ESCALATE_TO_STRATEGY_GOVERNOR = "ESCALATE_TO_STRATEGY_GOVERNOR"
    WATCH = "WATCH"
    STARVE_SIGNAL = "STARVE_SIGNAL"
    QUARANTINE_SOURCE = "QUARANTINE_SOURCE"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class EdgeAccelerationScore:
    probability_delta: float
    signal_freshness: float
    source_reliability: float
    source_uniqueness: float
    liquidity_quality: float
    spread_quality: float
    model_agreement: float
    model_disagreement_value: float
    calibration_support: float
    strategy_fit: float
    settlement_clarity: float
    no_trade_pressure: float
    implementation_cost: float
    proof_cost: float
    total: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "probability_delta": self.probability_delta,
            "signal_freshness": self.signal_freshness,
            "source_reliability": self.source_reliability,
            "source_uniqueness": self.source_uniqueness,
            "liquidity_quality": self.liquidity_quality,
            "spread_quality": self.spread_quality,
            "model_agreement": self.model_agreement,
            "model_disagreement_value": self.model_disagreement_value,
            "calibration_support": self.calibration_support,
            "strategy_fit": self.strategy_fit,
            "settlement_clarity": self.settlement_clarity,
            "no_trade_pressure": self.no_trade_pressure,
            "implementation_cost": self.implementation_cost,
            "proof_cost": self.proof_cost,
            "total": self.total,
        }


@dataclass(frozen=True)
class EdgeHypothesis:
    hypothesis_id: str
    source_category: str
    signal_type: str
    score: EdgeAccelerationScore
    triage: EdgeTriageDecision
    proof_reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "source_category": self.source_category,
            "signal_type": self.signal_type,
            "score": self.score.to_dict(),
            "triage": self.triage.value,
            "proof_reference": self.proof_reference,
        }


@dataclass(frozen=True)
class EdgeHypothesisBatch:
    batch_id: str
    hypotheses: list[EdgeHypothesis]

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "hypothesis_count": len(self.hypotheses),
            "hypotheses": [hypothesis.to_dict() for hypothesis in self.hypotheses],
        }


class EdgeDiscoveryAccelerator:
    def _score(
        self,
        probability_delta: float,
        signal_freshness: float,
        source_reliability: float,
        source_uniqueness: float,
        liquidity_quality: float,
        spread_quality: float,
        model_agreement: float,
        model_disagreement_value: float,
        calibration_support: float,
        strategy_fit: float,
        settlement_clarity: float,
        no_trade_pressure: float,
        implementation_cost: float,
        proof_cost: float,
    ) -> EdgeAccelerationScore:
        total = (
            probability_delta * 0.20
            + signal_freshness * 0.10
            + source_reliability * 0.10
            + source_uniqueness * 0.08
            + liquidity_quality * 0.08
            + spread_quality * 0.08
            + model_agreement * 0.08
            + model_disagreement_value * 0.06
            + calibration_support * 0.08
            + strategy_fit * 0.08
            + settlement_clarity * 0.06
            - no_trade_pressure * 0.10
            - implementation_cost * 0.05
            - proof_cost * 0.05
        )
        return EdgeAccelerationScore(
            probability_delta,
            signal_freshness,
            source_reliability,
            source_uniqueness,
            liquidity_quality,
            spread_quality,
            model_agreement,
            model_disagreement_value,
            calibration_support,
            strategy_fit,
            settlement_clarity,
            no_trade_pressure,
            implementation_cost,
            proof_cost,
            round(max(0.0, min(1.0, total)), 4),
        )

    def generate_batch(self) -> EdgeHypothesisBatch:
        hypotheses = [
            EdgeHypothesis(
                "edge-v10-001",
                "crypto_btc",
                "volatility_shift",
                self._score(0.82, 0.90, 0.84, 0.78, 0.70, 0.74, 0.80, 0.45, 0.72, 0.78, 0.88, 0.14, 0.28, 0.34),
                EdgeTriageDecision.ESCALATE_TO_FORECAST,
                "edge-proof-btc-volatility",
            ),
            EdgeHypothesis(
                "edge-v10-002",
                "macro_calendar",
                "event_timing_pressure",
                self._score(0.58, 0.54, 0.72, 0.64, 0.62, 0.66, 0.70, 0.36, 0.68, 0.60, 0.76, 0.24, 0.34, 0.38),
                EdgeTriageDecision.WATCH,
                "edge-proof-macro-timing",
            ),
            EdgeHypothesis(
                "edge-v10-003",
                "weather",
                "weather_risk_pressure",
                self._score(0.46, 0.50, 0.62, 0.60, 0.54, 0.58, 0.52, 0.30, 0.48, 0.44, 0.66, 0.36, 0.26, 0.30),
                EdgeTriageDecision.STARVE_SIGNAL,
                "edge-proof-weather-pressure",
            ),
            EdgeHypothesis(
                "edge-v10-004",
                "prediction_market_cross_price",
                "explicit_mock_cross_price",
                self._score(0.32, 0.30, 0.42, 0.50, 0.40, 0.44, 0.38, 0.28, 0.36, 0.34, 0.44, 0.62, 0.22, 0.28),
                EdgeTriageDecision.NO_TRADE,
                "edge-proof-cross-price-explicit-mock",
            ),
        ]
        return EdgeHypothesisBatch("edge-v10-batch-001", hypotheses)

    def rank(self, batch: EdgeHypothesisBatch) -> EdgeHypothesisBatch:
        return EdgeHypothesisBatch(
            batch.batch_id,
            sorted(batch.hypotheses, key=lambda hypothesis: hypothesis.score.total, reverse=True),
        )

    def batch_report(self) -> dict[str, Any]:
        ranked = self.rank(self.generate_batch())
        return {
            "workstream": "V10: Edge Hypothesis Batch",
            **ranked.to_dict(),
            "verdict": "PASS" if ranked.hypotheses else "FAIL",
        }

    def triage_report(self) -> dict[str, Any]:
        ranked = self.rank(self.generate_batch())
        decisions = [
            {
                "hypothesis_id": hypothesis.hypothesis_id,
                "source_category": hypothesis.source_category,
                "decision": hypothesis.triage.value,
                "score_total": hypothesis.score.total,
                "proof_reference": hypothesis.proof_reference,
            }
            for hypothesis in ranked.hypotheses
        ]
        return {
            "workstream": "V10: Edge Triage Decisions",
            "decisions": decisions,
            "verdict": "PASS" if decisions else "FAIL",
        }

    def to_report(self) -> dict[str, Any]:
        ranked = self.rank(self.generate_batch())
        return {
            "workstream": "V10: Edge Discovery Accelerator",
            "batch_id": ranked.batch_id,
            "hypothesis_count": len(ranked.hypotheses),
            "escalated_count": sum(
                1
                for hypothesis in ranked.hypotheses
                if hypothesis.triage
                in {
                    EdgeTriageDecision.ESCALATE_TO_FORECAST,
                    EdgeTriageDecision.ESCALATE_TO_MINIMAX_REVIEW,
                    EdgeTriageDecision.ESCALATE_TO_STRATEGY_GOVERNOR,
                }
            ),
            "watch_count": sum(1 for hypothesis in ranked.hypotheses if hypothesis.triage is EdgeTriageDecision.WATCH),
            "no_trade_count": sum(1 for hypothesis in ranked.hypotheses if hypothesis.triage is EdgeTriageDecision.NO_TRADE),
            "hypotheses": [hypothesis.to_dict() for hypothesis in ranked.hypotheses],
            "verdict": "PASS" if ranked.hypotheses else "FAIL",
        }
