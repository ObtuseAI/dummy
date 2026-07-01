"""Tests for the edge intelligence engine."""

import pytest

from predator_mesh.edge.engine import EdgeIntelligenceEngine
from predator_mesh.edge.models import (
    EdgeCandidate,
    EdgeDecision,
    EdgeScore,
    MarketTerrainSnapshot,
)
from predator_mesh.signals.models import NormalizedSignal, SignalType


def test_engine_scores_empty_signals_as_starve_signal() -> None:
    engine = EdgeIntelligenceEngine()
    terrain = MarketTerrainSnapshot()
    candidates = engine.score([], terrain)
    assert len(candidates) == 1
    assert candidates[0].decision == EdgeDecision.STARVE_SIGNAL
    assert candidates[0].score.composite == 0.0


def test_engine_produces_candidate_with_score() -> None:
    engine = EdgeIntelligenceEngine()
    terrain = MarketTerrainSnapshot(volatility_regime="low", liquidity_state="deep")
    signals = [
        NormalizedSignal(
            signal_type=SignalType.PRICE_MOVE,
            strength=0.8,
            confidence=0.9,
        ),
        NormalizedSignal(
            signal_type=SignalType.VOLUME_SPIKE,
            strength=0.7,
            confidence=0.8,
        ),
    ]
    candidates = engine.score(signals, terrain)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert isinstance(candidate, EdgeCandidate)
    assert isinstance(candidate.score, EdgeScore)
    assert 0.0 <= candidate.score.composite <= 1.0
    assert candidate.decision in set(EdgeDecision)
    assert candidate.rationale != ""


def test_engine_quarantines_in_extreme_volatility() -> None:
    engine = EdgeIntelligenceEngine()
    terrain = MarketTerrainSnapshot(volatility_regime="extreme")
    signals = [
        NormalizedSignal(
            signal_type=SignalType.PRICE_MOVE,
            strength=0.9,
            confidence=0.95,
        )
    ]
    candidates = engine.score(signals, terrain)
    assert candidates[0].decision == EdgeDecision.QUARANTINE_SOURCE


def test_engine_quarantines_on_high_event_risk() -> None:
    engine = EdgeIntelligenceEngine()
    terrain = MarketTerrainSnapshot(event_risk="high")
    signals = [
        NormalizedSignal(
            signal_type=SignalType.PRICE_MOVE,
            strength=0.9,
            confidence=0.95,
        )
    ]
    candidates = engine.score(signals, terrain)
    assert candidates[0].decision == EdgeDecision.QUARANTINE_SOURCE


def test_engine_penalizes_thin_liquidity() -> None:
    engine = EdgeIntelligenceEngine()
    deep = MarketTerrainSnapshot(liquidity_state="deep", volatility_regime="low")
    thin = MarketTerrainSnapshot(liquidity_state="thin", volatility_regime="low")
    signals = [
        NormalizedSignal(
            signal_type=SignalType.PRICE_MOVE,
            strength=0.8,
            confidence=0.9,
        )
    ]
    deep_score = engine.score(signals, deep)[0].score.composite
    thin_score = engine.score(signals, thin)[0].score.composite
    assert thin_score < deep_score


def test_engine_consensus_divergence_increases_with_disagreement() -> None:
    engine = EdgeIntelligenceEngine()
    terrain = MarketTerrainSnapshot()
    agreeing = [
        NormalizedSignal(signal_type=SignalType.PRICE_MOVE, strength=0.8, confidence=0.9),
        NormalizedSignal(signal_type=SignalType.PRICE_MOVE, strength=0.85, confidence=0.9),
    ]
    disagreeing = [
        NormalizedSignal(signal_type=SignalType.PRICE_MOVE, strength=0.9, confidence=0.9),
        NormalizedSignal(signal_type=SignalType.PRICE_MOVE, strength=-0.9, confidence=0.9),
    ]
    assert (
        engine.score(disagreeing, terrain)[0].score.consensus_divergence
        > engine.score(agreeing, terrain)[0].score.consensus_divergence
    )


def test_engine_anomaly_strength_detects_anomaly_signals() -> None:
    engine = EdgeIntelligenceEngine()
    terrain = MarketTerrainSnapshot()
    signals = [
        NormalizedSignal(signal_type=SignalType.ANOMALY, strength=0.9, confidence=0.9),
    ]
    candidate = engine.score(signals, terrain)[0]
    assert candidate.score.anomaly_strength > 0.0


def test_engine_score_many_batches() -> None:
    engine = EdgeIntelligenceEngine()
    terrain = MarketTerrainSnapshot()
    batches = [
        [NormalizedSignal(signal_type=SignalType.PRICE_MOVE, strength=0.5, confidence=0.7)],
        [NormalizedSignal(signal_type=SignalType.ANOMALY, strength=0.6, confidence=0.7)],
    ]
    candidates = engine.score_many(batches, terrain)
    assert len(candidates) == 2
