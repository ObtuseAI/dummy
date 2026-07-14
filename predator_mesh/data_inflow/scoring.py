"""Source scoring, tiering, promotion and pruning decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from predator_mesh.data_inflow.models import DataSourceCandidate, SourceStatus


class SourceTier(str, Enum):
    """Scoring tier for a data source."""

    PROMOTE = "promote"
    CANDIDATE = "candidate"
    PRUNE = "prune"


class DataSourceScore(BaseModel):
    """Decomposed score for a data source candidate."""

    source_id: str
    reliability_score: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    latency_score: float = Field(ge=0.0, le=1.0)
    uniqueness_score: float = Field(ge=0.0, le=1.0)
    edge_contribution_score: float = Field(ge=0.0, le=1.0)
    composite_score: float = Field(ge=0.0, le=1.0)
    tier: SourceTier = SourceTier.CANDIDATE
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rationale: str = ""


class SourceScorer(BaseModel):
    """Score candidates across reliability, freshness, latency, uniqueness,
    and edge contribution.
    """

    reliability_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    freshness_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    latency_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    uniqueness_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    edge_contribution_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    promote_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    prune_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    freshness_half_life_s: float = Field(default=60.0, gt=0.0)
    latency_target_ms: float = Field(default=200.0, gt=0.0)

    def _freshness_score(self, freshness_s: float) -> float:
        """Decay freshness score exponentially with stale time."""
        import math

        return math.exp(-freshness_s / self.freshness_half_life_s)

    def _latency_score(self, latency_ms: float) -> float:
        """Latency score: 1.0 at 0ms, decaying toward target."""
        if latency_ms <= 0:
            return 1.0
        return self.latency_target_ms / (self.latency_target_ms + latency_ms)

    def score(self, candidate: DataSourceCandidate) -> DataSourceScore:
        """Return a fully populated score for ``candidate``."""
        rel = max(0.0, min(1.0, candidate.reliability))
        fresh = max(0.0, min(1.0, self._freshness_score(candidate.freshness_s)))
        latency = max(0.0, min(1.0, self._latency_score(candidate.latency_ms)))
        unique = max(0.0, min(1.0, candidate.uniqueness))
        edge = max(0.0, min(1.0, candidate.edge_contribution))

        composite = (
            rel * self.reliability_weight
            + fresh * self.freshness_weight
            + latency * self.latency_weight
            + unique * self.uniqueness_weight
            + edge * self.edge_contribution_weight
        )
        composite = round(max(0.0, min(1.0, composite)), 6)

        if composite >= self.promote_threshold:
            tier = SourceTier.PROMOTE
        elif composite <= self.prune_threshold:
            tier = SourceTier.PRUNE
        else:
            tier = SourceTier.CANDIDATE

        rationale = (
            f"composite={composite:.3f} rel={rel:.2f} fresh={fresh:.2f} "
            f"lat={latency:.2f} unique={unique:.2f} edge={edge:.2f}"
        )

        return DataSourceScore(
            source_id=candidate.source_id,
            reliability_score=rel,
            freshness_score=fresh,
            latency_score=latency,
            uniqueness_score=unique,
            edge_contribution_score=edge,
            composite_score=composite,
            tier=tier,
            rationale=rationale,
        )

    def score_many(
        self,
        candidates: list[DataSourceCandidate],
    ) -> list[DataSourceScore]:
        """Score a batch of candidates."""
        return [self.score(c) for c in candidates]

    def decide(
        self,
        candidate: DataSourceCandidate,
        score: DataSourceScore | None = None,
    ) -> tuple[SourceStatus, str]:
        """Return promotion/pruning decision for a candidate."""
        score = score or self.score(candidate)
        if score.tier == SourceTier.PROMOTE:
            return SourceStatus.PROMOTED, f"Promoted: {score.rationale}"
        if score.tier == SourceTier.PRUNE:
            return SourceStatus.PRUNED, f"Pruned below threshold: {score.rationale}"
        return SourceStatus.CANDIDATE, f"Remains candidate: {score.rationale}"


class PromotionPruningEngine(BaseModel):
    """Apply scorer decisions to candidates and update their statuses."""

    scorer: SourceScorer = Field(default_factory=SourceScorer)

    def evaluate(
        self,
        candidates: list[DataSourceCandidate],
    ) -> list[DataSourceCandidate]:
        """Score each candidate and update its status/reason fields."""
        for candidate in candidates:
            score = self.scorer.score(candidate)
            status, reason = self.scorer.decide(candidate, score)
            candidate.status = status
            candidate.score = score.model_dump()
            if status == SourceStatus.PROMOTED:
                candidate.promotion_reason = reason
                candidate.prune_reason = None
            elif status == SourceStatus.PRUNED:
                candidate.prune_reason = reason
                candidate.promotion_reason = None
            else:
                candidate.promotion_reason = None
                candidate.prune_reason = None
            candidate.bump_updated_at()
        return candidates

    def prune(self, candidates: list[DataSourceCandidate]) -> list[DataSourceCandidate]:
        """Return candidates that are currently marked PRUNED."""
        return [c for c in candidates if c.status == SourceStatus.PRUNED]

    def promote(self, candidates: list[DataSourceCandidate]) -> list[DataSourceCandidate]:
        """Return candidates that are currently marked PROMOTED."""
        return [c for c in candidates if c.status == SourceStatus.PROMOTED]
