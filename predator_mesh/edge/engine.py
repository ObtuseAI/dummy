"""Edge intelligence engine: score signals against terrain."""

from __future__ import annotations

from typing import Any

from predator_mesh.edge.models import (
    EdgeCandidate,
    EdgeDecision,
    EdgeScore,
    MarketTerrainSnapshot,
)
from predator_mesh.signals.models import NormalizedSignal, SignalType


class EdgeIntelligenceEngine:
    """Score normalized signals and terrain to produce edge candidates.

    The engine is deterministic and makes no live calls. It does not place
    orders or output raw account/position data.
    """

    def __init__(
        self,
        watch_threshold: float = 0.35,
        small_pilot_threshold: float = 0.55,
        full_pilot_threshold: float = 0.75,
        block_threshold: float = 0.15,
    ) -> None:
        self.watch_threshold = watch_threshold
        self.small_pilot_threshold = small_pilot_threshold
        self.full_pilot_threshold = full_pilot_threshold
        self.block_threshold = block_threshold

    def _aggregate_signal_strength(
        self,
        signals: list[NormalizedSignal],
    ) -> tuple[float, float]:
        """Return aggregated strength and confidence across signals."""
        if not signals:
            return 0.0, 0.0
        total_confidence = sum(s.confidence for s in signals) or 1.0
        weighted_strength = (
            sum(s.strength * s.confidence for s in signals) / total_confidence
        )
        mean_confidence = total_confidence / len(signals)
        return (
            max(-1.0, min(1.0, weighted_strength)),
            max(0.0, min(1.0, mean_confidence)),
        )

    def _anomaly_strength(self, signals: list[NormalizedSignal]) -> float:
        """Measure concentration of anomaly/volume/volatility signals."""
        anomaly_types = {
            SignalType.ANOMALY,
            SignalType.VOLUME_SPIKE,
            SignalType.VOLATILITY_REGIME,
            SignalType.LIQUIDITY_STRESS,
        }
        if not signals:
            return 0.0
        count = sum(1 for s in signals if s.signal_type in anomaly_types)
        return min(1.0, count / max(1.0, len(signals) / 2.0))

    def _consensus_divergence(
        self,
        signals: list[NormalizedSignal],
    ) -> float:
        """Measure dispersion of signal strength (higher = more disagreement)."""
        if len(signals) < 2:
            return 0.0
        strengths = [s.strength for s in signals]
        mean = sum(strengths) / len(strengths)
        variance = sum((x - mean) ** 2 for x in strengths) / len(strengths)
        return min(1.0, variance * 4.0)

    def _terrain_penalty(
        self,
        terrain: MarketTerrainSnapshot,
    ) -> float:
        """Reduce score in adverse terrain; bonus in favorable terrain."""
        penalty = 0.0
        if terrain.volatility_regime in {"elevated", "extreme"}:
            penalty += 0.15
        if terrain.liquidity_state == "thin":
            penalty += 0.15
        if terrain.event_risk in {"medium", "high"}:
            penalty += 0.10
        if terrain.trend_direction == "sideways":
            penalty += 0.05
        return min(1.0, penalty)

    def score(
        self,
        signals: list[NormalizedSignal],
        terrain: MarketTerrainSnapshot,
    ) -> list[EdgeCandidate]:
        """Produce one or more scored edge candidates from signals and terrain.

        For simplicity the engine returns a single aggregate candidate when
        signals are present, plus a noise candidate when no signals are given.
        """
        if not signals:
            return [
                EdgeCandidate(
                    signals=[],
                    terrain=terrain,
                    score=EdgeScore(),
                    decision=EdgeDecision.PASS,
                    rationale="no signals to score",
                )
            ]

        strength, confidence = self._aggregate_signal_strength(signals)
        anomaly = self._anomaly_strength(signals)
        divergence = self._consensus_divergence(signals)
        penalty = self._terrain_penalty(terrain)

        conviction = confidence * (1.0 - divergence)
        risk_adjusted_return = strength * conviction * (1.0 - penalty)
        time_horizon = 0.5 + (0.3 if terrain.volatility_regime == "low" else 0.0)
        composite = max(
            0.0,
            min(
                1.0,
                (
                    conviction * 0.30
                    + abs(risk_adjusted_return) * 0.30
                    + anomaly * 0.25
                    + (1.0 - divergence) * 0.15
                )
                - penalty,
            ),
        )

        score = EdgeScore(
            conviction=round(conviction, 6),
            risk_adjusted_return=round(risk_adjusted_return, 6),
            time_horizon=round(time_horizon, 6),
            anomaly_strength=round(anomaly, 6),
            consensus_divergence=round(divergence, 6),
            composite=round(composite, 6),
        )

        decision = self._decide(composite, terrain)
        rationale = (
            f"composite={composite:.3f} strength={strength:.2f} "
            f"confidence={confidence:.2f} anomaly={anomaly:.2f} "
            f"divergence={divergence:.2f} terrain_penalty={penalty:.2f}"
        )

        candidate = EdgeCandidate(
            signals=signals,
            terrain=terrain,
            score=score,
            decision=decision,
            rationale=rationale,
            proof_refs=[s.signal_id for s in signals],
        )
        return [candidate]

    def _decide(
        self,
        composite: float,
        terrain: MarketTerrainSnapshot,
    ) -> EdgeDecision:
        """Map composite score and terrain to a discrete decision."""
        if terrain.event_risk == "high" or terrain.volatility_regime == "extreme":
            return EdgeDecision.BLOCK
        if composite <= self.block_threshold:
            return EdgeDecision.PASS
        if composite <= self.watch_threshold:
            return EdgeDecision.WATCH
        if composite <= self.small_pilot_threshold:
            return EdgeDecision.WATCH
        if composite <= self.full_pilot_threshold:
            return EdgeDecision.SMALL_PILOT
        return EdgeDecision.FULL_PILOT

    def score_many(
        self,
        signal_batches: list[list[NormalizedSignal]],
        terrain: MarketTerrainSnapshot,
    ) -> list[EdgeCandidate]:
        """Score multiple signal groups against the same terrain."""
        candidates: list[EdgeCandidate] = []
        for batch in signal_batches:
            candidates.extend(self.score(batch, terrain))
        return candidates
