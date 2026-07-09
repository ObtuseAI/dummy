from __future__ import annotations

from scripts.generate_v14_reports import generate_v9_mesh_status_report_v14


def test_v9_mesh_still_passes_v14() -> None:
    report = generate_v9_mesh_status_report_v14()

    assert report["verdict"] == "PASS"
    assert report["v9_mesh_status"] in {"PASS", "UNKNOWN"}
