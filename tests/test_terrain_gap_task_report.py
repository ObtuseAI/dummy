from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_terrain_gap_task_report_focuses_on_terrain_improvements() -> None:
    report = assert_v20_report("terrain_gap_task_report_v1.json", "tasks")
    assert all("terrain_gap" in task["task_id"] for task in report["tasks"])
