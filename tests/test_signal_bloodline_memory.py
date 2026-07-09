from __future__ import annotations

from predator_mesh.v10.bloodlines import BloodlineMemory


def test_signal_bloodline_memory_scores_signals() -> None:
    report = BloodlineMemory().signal_report()
    assert report["verdict"] == "PASS"
    assert report["bloodlines"]
    assert all(item["signal_type"] for item in report["bloodlines"])
