from __future__ import annotations

from predator_mesh.v10.bloodlines import BloodlineMemory


def test_source_bloodline_memory_scores_sources() -> None:
    report = BloodlineMemory().source_report()
    assert report["verdict"] == "PASS"
    assert report["bloodlines"]
    for bloodline in report["bloodlines"]:
        assert bloodline["source_category"]
        assert bloodline["score"]["total"] >= 0
