from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_workflow_task_queue_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["workflow_task_queue_status"] == "PASS"
    assert report["deterministic_from_artifacts"] is True
    assert report["blocked_real_probe_task"]["blocker"] == "MISSING_EXACT_OPERATOR_GATE"
    assert "REAL_PROBE_RUN" in report["task_categories"]
    assert report["live_trading_task_queued"] is False
    assert report["browser_task_queued"] is False
