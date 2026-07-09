from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_source_truth_workflow_v18() -> None:
    report = assert_current_test_report(__file__)
    assert report["source_truth_workflow_v18_status"] == "PASS"
    assert report["distinguishes_fake_pipeline_from_live_public"] is True
    assert report["recommended_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["can_recommend_live_trading"] is False
