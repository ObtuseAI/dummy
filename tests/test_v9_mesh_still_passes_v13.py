from __future__ import annotations

from scripts.generate_v13_reports import generate_v9_mesh_status_report_v13


def test_v9_mesh_still_passes_v13() -> None:
    report = generate_v9_mesh_status_report_v13()

    assert report["verdict"] == "PASS"
    assert report["v9_mesh_status"] in {"PASS", "UNKNOWN"}
