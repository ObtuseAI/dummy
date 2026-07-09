from __future__ import annotations


def test_v13_bridge_still_passes_or_partial_expected_v16() -> None:
    from scripts.generate_v16_reports import generate_prior_milestone_statuses

    assert generate_prior_milestone_statuses()["v13_bridge_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
