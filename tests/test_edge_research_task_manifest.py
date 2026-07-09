from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_edge_research_task_manifest_has_ranked_work_items() -> None:
    report = assert_v20_report("edge_research_task_manifest_v1.json", "tasks")
    assert report["task_count"] > 0
    assert report["tasks"][0]["priority"] >= report["tasks"][-1]["priority"]

