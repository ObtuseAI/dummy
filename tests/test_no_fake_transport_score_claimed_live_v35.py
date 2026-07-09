from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_no_fake_transport_score_claimed_live_v35() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["fake_transport_score_claimed_live"] is False
    assert report["execution_bridge_present"] is False


def test_enabled_path_marks_pipeline_score_only() -> None:
    from tests.v35_test_helpers import assert_v35_report_named

    audit = assert_v35_report_named("enabled_path_evidence_mode_audit_v1_report.json")
    assert audit["fake_transport_score_not_claimed_live"] is True
    elig = assert_v35_report_named("live_score_sample_eligibility_report.json")
    assert elig["sample_mode"] == "PIPELINE_SCORE_ONLY"
