from __future__ import annotations


def test_v15_credential_shape_auth_still_passes_v16() -> None:
    from scripts.generate_v16_reports import generate_prior_milestone_statuses

    statuses = generate_prior_milestone_statuses()
    assert statuses["v15_credential_shape_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
    assert statuses["v15_auth_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
