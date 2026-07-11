from __future__ import annotations

from archive.report_scripts.generate_v11_reports import generate_v9_mesh_status_report_v11


def test_v9_mesh_still_passes_v11() -> None:
    report = generate_v9_mesh_status_report_v11()
    assert report["verdict"] == "PASS"
    assert report["v9_mesh_status"] == "PASS"
