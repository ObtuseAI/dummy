from __future__ import annotations

from predator_mesh.v10.edge_accelerator import EdgeDiscoveryAccelerator


def test_edge_hypothesis_batch_report() -> None:
    report = EdgeDiscoveryAccelerator().batch_report()
    assert report["verdict"] == "PASS"
    assert report["hypothesis_count"] > 0
    assert all("hypothesis_id" in h for h in report["hypotheses"])
