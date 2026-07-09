from __future__ import annotations

from predator_mesh.v10.bloodlines import BloodlineMemory


def test_bloodline_promotion_pruning_report() -> None:
    report = BloodlineMemory().promotion_pruning_report()
    assert report["verdict"] == "PASS"
    assert report["promotion_decisions"]
    assert report["pruning_decisions"]
