from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_evidence_closure_workflow_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["evidence_closure_workflow_status"] == "PASS_BLOCKED"
    assert report["live_score_eligible_evidence_modes"] == ["LIVE_PUBLIC_PROBE_RESULT"]
    assert report["live_scored_count"] == 0
    assert report["blocker"] == "NO_REAL_LIVE_PUBLIC_EVIDENCE"
