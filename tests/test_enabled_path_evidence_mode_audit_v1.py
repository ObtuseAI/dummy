from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_enabled_path_evidence_mode_audit_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["evidence_mode"] == "FAKE_TRANSPORT_TEST"
    assert report["live_public_eligible"] is False
    assert report["fake_transport_score_not_claimed_live"] is True
    assert report["execution_bridge_present"] is False


def test_enabled_evidence_mode_blocker_marks_fake_transport() -> None:
    from tests.v35_test_helpers import assert_v35_report_named

    report = assert_v35_report_named("enabled_evidence_mode_blocker_report.json")
    assert report["blocker"] == "FAKE_TRANSPORT_ONLY_CANNOT_CLAIM_LIVE"
