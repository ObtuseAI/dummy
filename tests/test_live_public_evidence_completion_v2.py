from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_live_public_evidence_completion_v2() -> None:
    report = assert_current_test_report(__file__)
    assert report["live_public_evidence_completion_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["eligible_evidence_mode"] == "LIVE_PUBLIC_PROBE_RESULT"
    assert report["fake_transport_evidence_entered"] is False


def test_live_public_evidence_completion_enabled_counts_only_live_public_results() -> None:
    report = v39_enabled_reports()["live_public_evidence_completion_v2_report.json"]
    assert report["live_public_evidence_completion_status"] == "PASS_LIVE_PUBLIC_EVIDENCE"
    assert report["real_evidence_count"] > 0
    assert report["eligible_evidence_mode"] == "LIVE_PUBLIC_PROBE_RESULT"
    assert report["fake_transport_evidence_entered"] is False
