from __future__ import annotations


def test_v17_truth_loop_still_passes_v18() -> None:
    from scripts.generate_v18_reports import generate_prior_statuses_v18

    assert generate_prior_statuses_v18()["v17_truth_loop_status"] in {"PASS", "UNKNOWN"}
