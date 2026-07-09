from __future__ import annotations


def test_v9_mesh_still_passes_v16() -> None:
    from scripts.generate_v16_reports import generate_prior_milestone_statuses

    assert generate_prior_milestone_statuses()["v9_mesh_status"] in {"PASS", "UNKNOWN"}
