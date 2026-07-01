"""Tests for the signal ontology."""

import pytest

from predator_mesh.signals.models import NormalizedSignal, SignalType


def test_signal_type_enum_values() -> None:
    assert SignalType.PRICE_MOVE.value == "price_move"
    assert SignalType.VOLUME_SPIKE.value == "volume_spike"
    assert SignalType.SENTIMENT_SHIFT.value == "sentiment_shift"
    assert SignalType.VOLATILITY_REGIME.value == "volatility_regime"
    assert SignalType.LIQUIDITY_STRESS.value == "liquidity_stress"
    assert SignalType.CALENDAR_EVENT.value == "calendar_event"
    assert SignalType.ANOMALY.value == "anomaly"
    assert SignalType.UNKNOWN.value == "unknown"


def test_normalized_signal_defaults() -> None:
    signal = NormalizedSignal()
    assert signal.signal_type == SignalType.UNKNOWN
    assert signal.strength == 0.0
    assert signal.confidence == 0.0
    assert signal.source_id == ""
    assert signal.source_category == ""
    assert signal.proof_refs == []
    assert signal.raw_payload_redacted == {}


def test_normalized_signal_bounds() -> None:
    signal = NormalizedSignal(strength=2.0, confidence=-0.5)
    assert signal.strength == 1.0
    assert signal.confidence == 0.0

    signal = NormalizedSignal(strength=-2.0, confidence=1.5)
    assert signal.strength == -1.0
    assert signal.confidence == 1.0


def test_normalized_signal_actionable() -> None:
    strong = NormalizedSignal(strength=0.8, confidence=0.9)
    assert strong.is_actionable()

    weak_strength = NormalizedSignal(strength=0.1, confidence=0.9)
    assert not weak_strength.is_actionable()

    weak_confidence = NormalizedSignal(strength=0.9, confidence=0.3)
    assert not weak_confidence.is_actionable()


def test_normalized_signal_model_dump_redacts() -> None:
    signal = NormalizedSignal(
        signal_type=SignalType.PRICE_MOVE,
        strength=0.5,
        confidence=0.8,
        source_id="src-1",
        source_category="kalshi",
        raw_payload_redacted={"public": "data"},
    )
    data = signal.model_dump()
    assert data["signal_type"] == "price_move"
    assert data["strength"] == 0.5
    assert data["raw_payload_redacted"] == {"public": "data"}
