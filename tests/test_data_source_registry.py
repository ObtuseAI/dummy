"""Tests for the data source registry."""

import pytest

from predator_mesh.data_inflow.adapters import MockDataAdapter
from predator_mesh.data_inflow.models import (
    DataSourceCandidate,
    SourceCategory,
    SourceStatus,
)
from predator_mesh.data_inflow.registry import DataSourceRegistry
from predator_mesh.data_inflow.scoring import SourceScorer


def test_registry_adds_and_gets_candidate() -> None:
    registry = DataSourceRegistry()
    candidate = DataSourceCandidate(name="test")
    registry.add(candidate)
    assert registry.get(candidate.source_id) is candidate


def test_registry_add_many() -> None:
    registry = DataSourceRegistry()
    candidates = [
        DataSourceCandidate(name="a"),
        DataSourceCandidate(name="b"),
    ]
    registry.add_many(candidates)
    assert len(registry.sources) == 2


def test_registry_list_filters_by_status() -> None:
    registry = DataSourceRegistry()
    promoted = DataSourceCandidate(name="promoted", status=SourceStatus.PROMOTED)
    pruned = DataSourceCandidate(name="pruned", status=SourceStatus.PRUNED)
    registry.add(promoted)
    registry.add(pruned)
    assert registry.list(status=SourceStatus.PROMOTED) == [promoted]
    assert registry.list(status=SourceStatus.PRUNED) == [pruned]


def test_registry_list_filters_by_category() -> None:
    registry = DataSourceRegistry()
    rss = DataSourceCandidate(name="rss", category=SourceCategory.RSS)
    mock = DataSourceCandidate(name="mock", category=SourceCategory.MOCK)
    registry.add(rss)
    registry.add(mock)
    assert registry.list(category="rss") == [rss]
    assert registry.list(category="mock") == [mock]


def test_registry_update() -> None:
    registry = DataSourceRegistry()
    candidate = DataSourceCandidate(name="old")
    registry.add(candidate)
    registry.update(candidate.source_id, name="new")
    assert registry.get(candidate.source_id).name == "new"


def test_registry_update_missing_raises() -> None:
    registry = DataSourceRegistry()
    with pytest.raises(KeyError):
        registry.update("missing")


def test_registry_remove() -> None:
    registry = DataSourceRegistry()
    candidate = DataSourceCandidate(name="to_remove")
    registry.add(candidate)
    removed = registry.remove(candidate.source_id)
    assert removed is candidate
    assert registry.get(candidate.source_id) is None


def test_registry_score_all() -> None:
    registry = DataSourceRegistry(scorer=SourceScorer(promote_threshold=0.99))
    candidate = DataSourceCandidate(name="mid")
    registry.add(candidate)
    registry.score_all()
    assert candidate.score is not None


@pytest.mark.asyncio
async def test_registry_discover_with_mock_adapter() -> None:
    registry = DataSourceRegistry()
    discovered = await registry.discover([MockDataAdapter()])
    assert len(discovered) == 2
    assert all(isinstance(c, DataSourceCandidate) for c in discovered)
    assert len(registry.sources) == 2


@pytest.mark.asyncio
async def test_registry_discover_graceful_adapter_failure() -> None:
    class FailingAdapter:
        name = "failing"
        category = SourceCategory.UNKNOWN
        adapter_type = "failing"

        async def fetch(self):
            raise RuntimeError("boom")

    registry = DataSourceRegistry()
    discovered = await registry.discover([FailingAdapter()])
    assert len(discovered) == 1
    assert discovered[0].name == "failing_error"
    assert discovered[0].reliability == 0.0


def test_registry_clear() -> None:
    registry = DataSourceRegistry()
    registry.add(DataSourceCandidate(name="x"))
    registry.clear()
    assert len(registry.sources) == 0
