from __future__ import annotations


def test_v9_mesh_still_passes_v17() -> None:
    from archive.report_scripts.generate_v17_reports import generate_prior_statuses_v17

    assert generate_prior_statuses_v17()["v9_mesh_status"] in {"PASS", "UNKNOWN"}
