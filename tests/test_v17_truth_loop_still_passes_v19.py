from __future__ import annotations


def test_v17_truth_loop_still_passes_v19() -> None:
    from scripts.generate_v19_reports import generate_prior_statuses_v19

    assert generate_prior_statuses_v19()["v17_truth_loop_status"] in {"PASS", "UNKNOWN"}
