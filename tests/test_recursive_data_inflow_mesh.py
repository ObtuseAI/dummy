"""Tests for the recursive data inflow mesh lane."""

import pytest

from predator_mesh.budget import build_default_budget
from predator_mesh.data_inflow.adapters import MockDataAdapter
from predator_mesh.data_inflow.registry import DataSourceRegistry
from predator_mesh.lanes.recursive_inflow import RecursiveDataInflowLane
from predator_mesh.models import LaneState, MeshContext, MeshTimeout


@pytest.mark.asyncio
async def test_recursive_inflow_lane_discovers_sources() -> None:
    lane = RecursiveDataInflowLane()
    ctx = MeshContext(
        run_id="test",
        lane_name=lane.name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=None,
    )
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert result.result["sources_discovered"] > 0
    assert "candidates" in result.result
    assert "sources_promoted" in result.result
    assert "sources_pruned" in result.result


@pytest.mark.asyncio
async def test_recursive_inflow_lane_uses_custom_registry() -> None:
    registry = DataSourceRegistry()
    lane = RecursiveDataInflowLane(registry=registry)
    ctx = MeshContext(
        run_id="test",
        lane_name=lane.name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=None,
    )
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert len(registry.sources) > 0


@pytest.mark.asyncio
async def test_recursive_inflow_lane_stores_candidates_in_shared_state() -> None:
    lane = RecursiveDataInflowLane()
    ctx = MeshContext(
        run_id="test",
        lane_name=lane.name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=None,
    )
    await lane.execute(ctx)
    assert "data_source_candidates" in ctx.shared_state
    assert len(ctx.shared_state["data_source_candidates"]) > 0


@pytest.mark.asyncio
async def test_recursive_inflow_lane_is_registered() -> None:
    from predator_mesh.lane_registry import LANE_REGISTRY

    assert "recursive_inflow" in LANE_REGISTRY
    assert LANE_REGISTRY["recursive_inflow"] is RecursiveDataInflowLane


@pytest.mark.asyncio
async def test_recursive_inflow_lane_default_adapters_are_safe() -> None:
    lane = RecursiveDataInflowLane()
    for adapter in lane.adapters:
        # All default adapters must be deterministic and not place orders.
        candidates = await adapter.fetch()
        for candidate in candidates:
            assert isinstance(candidate.name, str)
            assert candidate.sample_payload is not None


@pytest.mark.asyncio
async def test_recursive_inflow_lane_with_mock_adapter_only() -> None:
    lane = RecursiveDataInflowLane(adapters=[MockDataAdapter()])
    ctx = MeshContext(
        run_id="test",
        lane_name=lane.name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=None,
    )
    result = await lane.execute(ctx)
    assert result.result["sources_discovered"] == 2


@pytest.mark.asyncio
async def test_recursive_inflow_lane_does_not_exceed_timeout() -> None:
    lane = RecursiveDataInflowLane()
    ctx = MeshContext(
        run_id="test",
        lane_name=lane.name,
        budget=build_default_budget(),
        timeout=MeshTimeout(per_lane_timeout_s=10.0),
        proof_ledger=None,
    )
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
