from __future__ import annotations


def test_v13_v15_credentials_historical_still_consistent_v17() -> None:
    from scripts.generate_v17_reports import generate_prior_statuses_v17

    status = generate_prior_statuses_v17()
    assert status["v13_bridge_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
    assert status["v15_credential_shape_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
    assert status["v15_auth_status"] in {"PASS", "PARTIAL", "UNKNOWN"}
