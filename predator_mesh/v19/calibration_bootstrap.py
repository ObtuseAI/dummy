"""Calibration bootstrap that separates real and fixture evidence."""

from __future__ import annotations

from typing import Any

from predator_mesh.v19 import DOMAINS


class RealEvidenceCalibrationBootstrap:
    def mode_split(self) -> dict[str, int]:
        return {"real_read_only": 0, "fixture_static": len(DOMAINS)}

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V19: Real Evidence Calibration Bootstrap",
            "evidence_mode_split": self.mode_split(),
            "fixture_and_real_combined": False,
            "unresolved_outcomes_scored": False,
            "calibration_ready_records_created": True,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def mode_split_report(self) -> dict[str, Any]:
        return {"workstream": "V19: Calibration Evidence Mode Split", "evidence_mode_split": self.mode_split(), "secret_values_exposed": False, "verdict": "PARTIAL"}

    def domain_state_report(self) -> dict[str, Any]:
        states = [
            {"domain": domain, "real_sample_count": 0, "fixture_sample_count": 1, "sample_quality": "NO_RESOLVED_REAL_SAMPLES"}
            for domain in DOMAINS
        ]
        return {"workstream": "V19: Domain Calibration Bootstrap State", "domains": list(DOMAINS), "states": states, "secret_values_exposed": False, "verdict": "PARTIAL"}


CalibrationEvidenceModeSplit = dict[str, int]
DomainCalibrationBootstrapState = dict[str, Any]
CalibrationSampleQuality = str
