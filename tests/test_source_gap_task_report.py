from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_gap_task_report_focuses_on_missing_sources() -> None:
    report = assert_v20_report("source_gap_task_report_v1.json", "tasks")
    assert all("source_gap" in task["task_id"] for task in report["tasks"])
