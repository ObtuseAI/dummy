"""Tests for signal normalization."""

import pytest

from predator_mesh.budget import build_default_budget
from predator_mesh.data_inflow.models import DataSourceCandidate, SourceCategory, SourceStatus
from predator_mesh.lanes.signal_normalization import SignalNormalizationLane
from predator_mesh.models import LaneState, MeshContext, MeshTimeout
from predator_mesh.signals.models import SignalType
from predator_mesh.signals.normalizer import SignalNormalizer


def test_normalizer_classifies_by_category() -> None:
    normalizer = SignalNormalizer()
    kalshi = DataSourceCandidate(name="k", category=SourceCategory.KALSHI)
    rss = DataSourceCandidate(name="r", category=SourceCategory.RSS)
    assert normalizer.classify(kalshi) == SignalType.PRICE_MOVE
    assert normalizer.classify(rss) == SignalType.SENTIMENT_SHIFT


def test_normalizer_strength_for_pruned_source() -> None:
    normalizer = SignalNormalizer()
    candidate = DataSourceCandidate(
        name="bad",
        category=SourceCategory.MOCK,
        status=SourceStatus.PRUNED,
        edge_contribution=1.0,
        uniqueness=1.0,
    )
    signal = normalizer.normalize(candidate)
    assert signal.strength < 0


def test_normalizer_confidence_bound() -> None:
    normalizer = SignalNormalizer()
    candidate = DataSourceCandidate(
        name="c",
        category=SourceCategory.RSS,
        reliability=1.0,
        freshness_s=0.0,
    )
    signal = normalizer.normalize(candidate)
    assert 0.0 <= signal.confidence <= 1.0


def test_normalizer_normalize_many() -> None:
    normalizer = SignalNormalizer()
    candidates = [
        DataSourceCandidate(name="a", category=SourceCategory.KALSHI),
        DataSourceCandidate(name="b", category=SourceCategory.RSS),
    ]
    signals = normalizer.normalize_many(candidates)
    assert len(signals) == 2
    assert signals[0].source_id == candidates[0].source_id
    assert signals[1].source_id == candidates[1].source_id


def test_normalizer_normalize_raw_payload() -> None:
    normalizer = SignalNormalizer()
    signal = normalizer.normalize_payload(
        source_id="src-1",
        source_category="rss",
        signal_type=SignalType.SENTIMENT_SHIFT,
        strength=0.7,
        confidence=0.8,
        payload={"headline": "sample"},
    )
    assert signal.signal_type == SignalType.SENTIMENT_SHIFT
    assert signal.strength == 0.7
    assert signal.confidence == 0.8
    assert signal.raw_payload_redacted == {"headline": "sample"}


@pytest.mark.asyncio
async def test_signal_normalization_lane_no_candidates() -> None:
    lane = SignalNormalizationLane()
    ctx = MeshContext(
        run_id="test",
        lane_name=lane.name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=None,
    )
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert result.result["signals_normalized"] == 0


@pytest.mark.asyncio
async def test_signal_normalization_lane_with_candidates() -> None:
    lane = SignalNormalizationLane()
    candidates = [
        DataSourceCandidate(name="a", category=SourceCategory.KALSHI),
        DataSourceCandidate(name="b", category=SourceCategory.RSS),
    ]
    ctx = MeshContext(
        run_id="test",
        lane_name=lane.name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=None,
        shared_state={"data_source_candidates": candidates},
    )
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert result.result["signals_normalized"] == 2
    assert "normalized_signals" in ctx.shared_state


@pytest.mark.asyncio
async def test_signal_normalization_lane_is_registered() -> None:
    from predator_mesh.lane_registry import LANE_REGISTRY

    assert "signal_normalization" in LANE_REGISTRY
    assert LANE_REGISTRY["signal_normalization"] is SignalNormalizationLane
