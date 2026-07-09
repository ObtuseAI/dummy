from __future__ import annotations

from predator_mesh.v10.telemetry import MeshThroughputTelemetry


def test_mesh_throughput_telemetry_report_tracks_counts() -> None:
    report = MeshThroughputTelemetry.sample().to_report()
    assert report["verdict"] == "PASS"
    assert report["mesh_cycle_duration_s"] >= 0
    assert report["packets_generated"] >= report["packets_promoted"]
    assert report["sources_discovered"] >= report["sources_promoted"]
