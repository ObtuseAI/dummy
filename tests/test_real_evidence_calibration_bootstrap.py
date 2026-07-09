from __future__ import annotations


def test_real_evidence_calibration_bootstrap_separates_fixture_and_real_samples() -> None:
    from predator_mesh.v19.calibration_bootstrap import RealEvidenceCalibrationBootstrap

    report = RealEvidenceCalibrationBootstrap().to_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["fixture_and_real_combined"] is False
