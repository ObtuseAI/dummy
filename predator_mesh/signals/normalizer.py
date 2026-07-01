"""Convert data source candidates into normalized signals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from predator_mesh.data_inflow.models import DataSourceCandidate
from predator_mesh.signals.models import NormalizedSignal, SignalType


class SignalNormalizer:
    """Map source candidates to a canonical signal ontology."""

    # Map source category to a default signal type.
    CATEGORY_SIGNAL_MAP: dict[str, SignalType] = {
        "kalshi": SignalType.PRICE_MOVE,
        "polymarket": SignalType.PRICE_MOVE,
        "rss": SignalType.SENTIMENT_SHIFT,
        "news_api": SignalType.SENTIMENT_SHIFT,
        "social": SignalType.SENTIMENT_SHIFT,
        "file": SignalType.ANOMALY,
        "mock": SignalType.ANOMALY,
        "unknown": SignalType.UNKNOWN,
    }

    def classify(self, candidate: DataSourceCandidate) -> SignalType:
        """Pick a signal type based on the candidate category."""
        return self.CATEGORY_SIGNAL_MAP.get(candidate.category.value, SignalType.UNKNOWN)

    def strength(self, candidate: DataSourceCandidate) -> float:
        """Derive signal strength from edge contribution and uniqueness.

        Strength is bounded to [-1, 1]. Most sources produce a positive
        directional hint; negative values are reserved for degraded sources.
        """
        if candidate.status.value == "pruned":
            return -0.5
        if candidate.status.value == "degraded":
            return -0.25
        raw = (candidate.edge_contribution + candidate.uniqueness) / 2.0
        return round(max(-1.0, min(1.0, raw)), 6)

    def confidence(self, candidate: DataSourceCandidate) -> float:
        """Confidence is driven primarily by reliability and freshness."""
        import math

        freshness = max(0.0, min(1.0, math.exp(-candidate.freshness_s / 60.0)))
        raw = (candidate.reliability * 0.6) + (freshness * 0.4)
        return round(max(0.0, min(1.0, raw)), 6)

    def normalize(self, candidate: DataSourceCandidate) -> NormalizedSignal:
        """Convert a single candidate into a normalized signal."""
        return NormalizedSignal(
            signal_type=self.classify(candidate),
            strength=self.strength(candidate),
            confidence=self.confidence(candidate),
            freshness=datetime.now(timezone.utc),
            source_id=candidate.source_id,
            source_category=candidate.category.value,
            proof_refs=[candidate.adapter_type],
            raw_payload_redacted=candidate.to_signal_input(),
            rationale=(
                f"normalized from {candidate.name} "
                f"({candidate.category.value}, status={candidate.status.value})"
            ),
        )

    def normalize_many(
        self,
        candidates: list[DataSourceCandidate],
    ) -> list[NormalizedSignal]:
        """Normalize a batch of candidates."""
        return [self.normalize(c) for c in candidates]

    def normalize_payload(
        self,
        source_id: str,
        source_category: str,
        signal_type: SignalType,
        strength: float,
        confidence: float,
        payload: dict[str, Any] | None = None,
    ) -> NormalizedSignal:
        """Normalize a raw public payload directly."""
        return NormalizedSignal(
            signal_type=signal_type,
            strength=max(-1.0, min(1.0, strength)),
            confidence=max(0.0, min(1.0, confidence)),
            freshness=datetime.now(timezone.utc),
            source_id=source_id,
            source_category=source_category,
            raw_payload_redacted=payload or {},
            rationale="normalized from raw public payload",
        )
