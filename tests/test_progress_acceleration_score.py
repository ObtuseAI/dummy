from __future__ import annotations

from predator_mesh.v10.telemetry import MeshThroughputTelemetry


def test_progress_acceleration_score_report() -> None:
    report = MeshThroughputTelemetry.sample().progress_score_report()
    assert report["verdict"] == "PASS"
    assert 0 <= report["progress_acceleration_score"] <= 1
    assert report["inputs"]["packets_promoted"] >= 0
