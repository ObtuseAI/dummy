from __future__ import annotations

from predator_mesh.v12.calibration import LiquidityCalibrationStore


def test_fill_quality_calibration_schema_tracks_expected_drag_and_probability() -> None:
    report = LiquidityCalibrationStore().fill_quality_schema_report()

    assert report["verdict"] == "PASS"
    assert "expected_fill_probability" in report["required_fields"]
    assert "expected_fill_drag" in report["required_fields"]
    assert "realized_fill_outcome" in report["required_fields"]
