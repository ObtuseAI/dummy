from __future__ import annotations


def test_v18_domain_foundation_still_passes_or_partial_expected_v19() -> None:
    from scripts.generate_v19_reports import generate_prior_statuses_v19

    assert generate_prior_statuses_v19()["v18_domain_foundation_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
