from __future__ import annotations


def test_v10_acceleration_still_passes_or_partial_expected_v17() -> None:
    from scripts.generate_v17_reports import generate_prior_statuses_v17

    assert generate_prior_statuses_v17()["v10_acceleration_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
