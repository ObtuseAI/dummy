from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_source_truth_v23_stability_engine_ranks_without_execution() -> None:
    report = assert_current_test_report(__file__)
    assert report["source_truth_v23_status"] == "PASS"
    assert "blocker_rate" in report["source_stability_dimensions"]
    assert report["source_truth_can_recommend_live_trading"] is False
    assert report["source_truth_to_execution_bridge_present"] is False
