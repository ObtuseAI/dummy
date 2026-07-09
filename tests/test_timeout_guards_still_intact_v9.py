from __future__ import annotations

from scripts.generate_v9_reports import generate_timeout_guards_still_intact_report_v9


def test_timeout_guards_still_intact_v9() -> None:
    report = generate_timeout_guards_still_intact_report_v9()
    assert report["verdict"] == "PASS"
    assert report["mesh_per_lane_timeout_s"] <= 20
    assert report["mesh_cycle_timeout_s"] <= 45
    assert report["smoke_call_timeout_s"] <= 20
    assert report["smoke_total_timeout_s"] <= 45
