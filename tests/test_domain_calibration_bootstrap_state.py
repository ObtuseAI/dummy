from __future__ import annotations

from v19_test_helpers import DOMAINS


def test_domain_calibration_bootstrap_state_tracks_low_sample_quality() -> None:
    from predator_mesh.v19.calibration_bootstrap import RealEvidenceCalibrationBootstrap

    report = RealEvidenceCalibrationBootstrap().domain_state_report()
    assert set(report["domains"]) == DOMAINS
    assert all(item["sample_quality"] in {"NO_RESOLVED_REAL_SAMPLES", "LOW_SAMPLE"} for item in report["states"])
