"""Tests for edge decision report output."""

import pytest

from predator_mesh.budget import build_default_budget
from predator_mesh.edge.engine import EdgeIntelligenceEngine
from predator_mesh.edge.models import EdgeCandidate, EdgeDecision, EdgeScore, MarketTerrainSnapshot
from predator_mesh.lanes.anomaly_mining import AnomalyMiningLane
from predator_mesh.models import LaneState, MeshContext, MeshTimeout
from predator_mesh.signals.models import NormalizedSignal, SignalType


def test_decision_report_contains_key_fields() -> None:
    candidate = EdgeCandidate(
        signals=[
            NormalizedSignal(signal_type=SignalType.PRICE_MOVE, strength=0.8, confidence=0.9)
        ],
        terrain=MarketTerrainSnapshot(),
        score=EdgeScore(
            conviction=0.8,
            risk_adjusted_return=0.6,
            time_horizon=0.7,
            anomaly_strength=0.2,
            consensus_divergence=0.1,
            composite=0.65,
        ),
        decision=EdgeDecision.SMALL_PILOT,
        rationale="favorable conditions",
    )
    report = candidate.to_decision_report()
    assert report["candidate_id"] == candidate.candidate_id
    assert report["decision"] == "small_pilot"
    assert report["score"]["composite"] == 0.65
    assert report["rationale"] == "favorable conditions"
    assert "timestamp" in report


def test_decision_report_score_matches_candidate() -> None:
    engine = EdgeIntelligenceEngine()
    signals = [
        NormalizedSignal(signal_type=SignalType.PRICE_MOVE, strength=0.9, confidence=0.95),
    ]
    candidate = engine.score(signals, MarketTerrainSnapshot(volatility_regime="low"))[0]
    report = candidate.to_decision_report()
    assert report["score"]["composite"] == candidate.score.composite
    assert report["decision"] == candidate.decision.value


@pytest.mark.asyncio
async def test_anomaly_mining_lane_produces_decision_report() -> None:
    lane = AnomalyMiningLane(
        engine=EdgeIntelligenceEngine(),
        terrain=MarketTerrainSnapshot(volatility_regime="low"),
    )
    signals = [
        NormalizedSignal(signal_type=SignalType.PRICE_MOVE, strength=0.9, confidence=0.95),
    ]
    ctx = MeshContext(
        run_id="test",
        lane_name=lane.name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=None,
        shared_state={"normalized_signals": signals},
    )
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert "anomalies" in result.result
    assert "candidates" in result.result
    assert len(result.result["candidates"]) == 1


@pytest.mark.asyncio
async def test_anomaly_mining_lane_no_signals() -> None:
    lane = AnomalyMiningLane()
    ctx = MeshContext(
        run_id="test",
        lane_name=lane.name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=None,
    )
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert result.result["anomalies"] == []
    assert result.result["candidates"] == []


@pytest.mark.asyncio
async def test_anomaly_mining_lane_is_registered() -> None:
    from predator_mesh.lane_registry import LANE_REGISTRY

    assert "anomaly_mining" in LANE_REGISTRY
    assert LANE_REGISTRY["anomaly_mining"] is AnomalyMiningLane
