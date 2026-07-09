from __future__ import annotations

from scripts.generate_v12_reports import generate_v9_mesh_status_report_v12


def test_v9_mesh_still_passes_v12() -> None:
    report = generate_v9_mesh_status_report_v12()

    assert report["verdict"] == "PASS"
    assert report["v9_mesh_status"] == "PASS"
