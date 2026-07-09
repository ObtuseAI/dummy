from __future__ import annotations


def test_calibration_evidence_mode_split_reports_real_and_fixture_counts() -> None:
    from predator_mesh.v19.calibration_bootstrap import RealEvidenceCalibrationBootstrap

    report = RealEvidenceCalibrationBootstrap().mode_split_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert "real_read_only" in report["evidence_mode_split"]
    assert "fixture_static" in report["evidence_mode_split"]
