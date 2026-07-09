from __future__ import annotations


def test_compounding_control_plane_prioritizes_source_gaps_without_execution() -> None:
    from predator_mesh.v20.compounding import AutonomousCompoundingControlPlaneV3

    report = AutonomousCompoundingControlPlaneV3().to_report()

    assert report["verdict"] == "PASS"
    assert report["proposal_count"] > 0
    assert report["live_execution_enabled"] is False
    assert report["top_objectives"][0]["kind"] in {"source_acquisition", "edge_terrain", "adapter_mining"}

