"""Tests for edge candidate manifest output."""

from predator_mesh.edge.engine import EdgeIntelligenceEngine
from predator_mesh.edge.models import EdgeCandidate, EdgeDecision, EdgeScore, MarketTerrainSnapshot
from predator_mesh.signals.models import NormalizedSignal, SignalType


def test_candidate_manifest_entry_is_redacted() -> None:
    signal = NormalizedSignal(
        signal_type=SignalType.PRICE_MOVE,
        strength=0.8,
        confidence=0.9,
        source_id="src-1",
        source_category="kalshi",
    )
    candidate = EdgeCandidate(
        signals=[signal],
        terrain=MarketTerrainSnapshot(),
        score=EdgeScore(composite=0.75),
        decision=EdgeDecision.SMALL_PILOT,
        rationale="strong directional signal",
        proof_refs=["proof-1"],
    )
    manifest = candidate.to_manifest_entry()
    assert manifest["candidate_id"] == candidate.candidate_id
    assert manifest["decision"] == "small_pilot"
    assert manifest["composite_score"] == 0.75
    assert manifest["signal_count"] == 1
    assert manifest["rationale"] == "strong directional signal"
    assert manifest["proof_refs"] == ["proof-1"]
    assert "volatility_regime" in manifest["terrain"]


def test_manifest_entry_does_not_contain_raw_signal_payload() -> None:
    signal = NormalizedSignal(
        signal_type=SignalType.SENTIMENT_SHIFT,
        strength=0.6,
        confidence=0.7,
        raw_payload_redacted={"public": "data"},
    )
    candidate = EdgeCandidate(signals=[signal], terrain=MarketTerrainSnapshot())
    manifest = candidate.to_manifest_entry()
    assert "raw_payload_redacted" not in manifest
    assert "signals" not in manifest


def test_manifest_entry_from_engine_candidate() -> None:
    engine = EdgeIntelligenceEngine()
    signals = [
        NormalizedSignal(signal_type=SignalType.PRICE_MOVE, strength=0.8, confidence=0.9),
    ]
    candidate = engine.score(signals, MarketTerrainSnapshot())[0]
    manifest = candidate.to_manifest_entry()
    assert "candidate_id" in manifest
    assert "decision" in manifest
    assert "composite_score" in manifest


def test_candidate_model_dump_contains_full_data() -> None:
    candidate = EdgeCandidate(
        signals=[
            NormalizedSignal(signal_type=SignalType.ANOMALY, strength=0.9, confidence=0.9)
        ],
        terrain=MarketTerrainSnapshot(),
        score=EdgeScore(composite=0.6),
        decision=EdgeDecision.WATCH,
    )
    data = candidate.model_dump()
    assert "signals" in data
    assert "score" in data
    assert "terrain" in data
    assert data["decision"] == "watch"
