"""In-memory registry for discovered and scored data sources."""

from __future__ import annotations

from typing import Any

from predator_mesh.data_inflow.adapters import BaseDataAdapter
from predator_mesh.data_inflow.models import DataSourceCandidate, SourceStatus
from predator_mesh.data_inflow.scoring import PromotionPruningEngine, SourceScorer


class DataSourceRegistry:
    """Store, score, and manage the lifecycle of data source candidates."""

    def __init__(
        self,
        scorer: SourceScorer | None = None,
        promotion_engine: PromotionPruningEngine | None = None,
    ) -> None:
        self._sources: dict[str, DataSourceCandidate] = {}
        self.scorer = scorer or SourceScorer()
        self.promotion_engine = promotion_engine or PromotionPruningEngine(
            scorer=self.scorer
        )

    @property
    def sources(self) -> dict[str, DataSourceCandidate]:
        """Read-only view of registered sources by source_id."""
        return self._sources.copy()

    def add(self, candidate: DataSourceCandidate) -> DataSourceCandidate:
        """Register a new candidate, replacing any existing entry with the same id."""
        self._sources[candidate.source_id] = candidate
        return candidate

    def add_many(
        self,
        candidates: list[DataSourceCandidate],
    ) -> list[DataSourceCandidate]:
        """Register multiple candidates."""
        return [self.add(c) for c in candidates]

    def update(
        self,
        source_id: str,
        **fields: Any,
    ) -> DataSourceCandidate:
        """Update specific fields of a registered candidate."""
        if source_id not in self._sources:
            raise KeyError(f"Source {source_id} not registered")
        candidate = self._sources[source_id]
        for key, value in fields.items():
            if hasattr(candidate, key):
                setattr(candidate, key, value)
        candidate.bump_updated_at()
        return candidate

    def get(self, source_id: str) -> DataSourceCandidate | None:
        """Fetch a candidate by id, or None if missing."""
        return self._sources.get(source_id)

    def list(
        self,
        status: SourceStatus | None = None,
        category: str | None = None,
    ) -> list[DataSourceCandidate]:
        """List registered candidates with optional filters."""
        result = list(self._sources.values())
        if status is not None:
            result = [c for c in result if c.status == status]
        if category is not None:
            result = [c for c in result if c.category.value == category]
        return result

    def remove(self, source_id: str) -> DataSourceCandidate | None:
        """Remove a candidate from the registry."""
        return self._sources.pop(source_id, None)

    def prune(self) -> list[DataSourceCandidate]:
        """Mark stale/unscored candidates as PRUNED using the promotion engine."""
        candidates = list(self._sources.values())
        self.promotion_engine.evaluate(candidates)
        pruned = self.promotion_engine.prune(candidates)
        for candidate in pruned:
            self._sources[candidate.source_id] = candidate
        return pruned

    def score_all(self) -> list[DataSourceCandidate]:
        """Score every registered candidate and persist updated statuses."""
        candidates = list(self._sources.values())
        self.promotion_engine.evaluate(candidates)
        for candidate in candidates:
            self._sources[candidate.source_id] = candidate
        return candidates

    async def discover(
        self,
        adapters: list[BaseDataAdapter],
    ) -> list[DataSourceCandidate]:
        """Run adapters, register discovered candidates, and score them."""
        discovered: list[DataSourceCandidate] = []
        for adapter in adapters:
            try:
                batch = await adapter.fetch()
            except Exception as exc:
                # Degrade individual adapters gracefully.
                batch = [
                    DataSourceCandidate(
                        name=f"{adapter.name}_error",
                        category=adapter.category,
                        adapter_type=adapter.adapter_type,
                        reliability=0.0,
                        freshness_s=float("inf"),
                        latency_ms=float("inf"),
                        uniqueness=0.0,
                        edge_contribution=0.0,
                        sample_payload={"error": str(exc)},
                    )
                ]
            discovered.extend(batch)
        self.add_many(discovered)
        self.score_all()
        return discovered

    def clear(self) -> None:
        """Remove all registered sources."""
        self._sources.clear()
