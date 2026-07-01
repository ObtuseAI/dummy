"""Tests for source promotion and pruning decisions."""

import pytest

from predator_mesh.data_inflow.models import DataSourceCandidate, SourceStatus
from predator_mesh.data_inflow.registry import DataSourceRegistry
from predator_mesh.data_inflow.scoring import PromotionPruningEngine, SourceScorer


def test_promote_high_quality_source() -> None:
    engine = PromotionPruningEngine(scorer=SourceScorer())
    candidate = DataSourceCandidate(
        name="great",
        reliability=1.0,
        freshness_s=0.0,
        latency_ms=1.0,
        uniqueness=1.0,
        edge_contribution=1.0,
    )
    engine.evaluate([candidate])
    assert candidate.status == SourceStatus.PROMOTED
    assert candidate.promotion_reason is not None
    assert candidate.prune_reason is None


def test_prune_low_quality_source() -> None:
    engine = PromotionPruningEngine(scorer=SourceScorer())
    candidate = DataSourceCandidate(
        name="awful",
        reliability=0.0,
        freshness_s=9999.0,
        latency_ms=9999.0,
        uniqueness=0.0,
        edge_contribution=0.0,
    )
    engine.evaluate([candidate])
    assert candidate.status == SourceStatus.PRUNED
    assert candidate.prune_reason is not None
    assert candidate.promotion_reason is None


def test_mid_quality_source_remains_candidate() -> None:
    engine = PromotionPruningEngine(scorer=SourceScorer())
    candidate = DataSourceCandidate(
        name="okay",
        reliability=0.5,
        freshness_s=30.0,
        latency_ms=100.0,
        uniqueness=0.5,
        edge_contribution=0.5,
    )
    engine.evaluate([candidate])
    assert candidate.status == SourceStatus.CANDIDATE
    assert candidate.promotion_reason is None
    assert candidate.prune_reason is None


def test_registry_prune_returns_pruned_sources() -> None:
    registry = DataSourceRegistry(scorer=SourceScorer())
    registry.add(
        DataSourceCandidate(
            name="prune_me",
            reliability=0.0,
            freshness_s=9999.0,
            latency_ms=9999.0,
            uniqueness=0.0,
            edge_contribution=0.0,
        )
    )
    pruned = registry.prune()
    assert len(pruned) == 1
    assert pruned[0].status == SourceStatus.PRUNED


def test_registry_promote_returns_promoted_sources() -> None:
    registry = DataSourceRegistry(scorer=SourceScorer())
    registry.add(
        DataSourceCandidate(
            name="promote_me",
            reliability=1.0,
            freshness_s=0.0,
            latency_ms=1.0,
            uniqueness=1.0,
            edge_contribution=1.0,
        )
    )
    registry.score_all()
    promoted = registry.promotion_engine.promote(list(registry.sources.values()))
    assert len(promoted) == 1
    assert promoted[0].status == SourceStatus.PROMOTED


def test_promotion_respects_custom_thresholds() -> None:
    scorer = SourceScorer(promote_threshold=0.99, prune_threshold=0.01)
    engine = PromotionPruningEngine(scorer=scorer)
    candidate = DataSourceCandidate(
        name="borderline",
        reliability=0.5,
        freshness_s=30.0,
        latency_ms=100.0,
        uniqueness=0.5,
        edge_contribution=0.5,
    )
    engine.evaluate([candidate])
    assert candidate.status == SourceStatus.CANDIDATE


@pytest.mark.asyncio
async def test_registry_discover_then_prune() -> None:
    from predator_mesh.data_inflow.adapters import MockDataAdapter

    registry = DataSourceRegistry(scorer=SourceScorer())
    await registry.discover([MockDataAdapter()])
    pruned = registry.prune()
    assert isinstance(pruned, list)
    for candidate in registry.sources.values():
        assert candidate.status in {
            SourceStatus.PROMOTED,
            SourceStatus.CANDIDATE,
            SourceStatus.PRUNED,
        }
