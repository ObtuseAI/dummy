"""Calibration identity for metacognitive forecasts themselves."""

from __future__ import annotations

from .state import MetaCalibrationEvidence


def unavailable_meta_calibration() -> MetaCalibrationEvidence:
    return MetaCalibrationEvidence(
        calibration_identity="phase5-metacognition-unavailable-v1",
        sample_size=0,
        brier=None,
        ece=None,
        verified=False,
        evidence_ids=(),
    )
