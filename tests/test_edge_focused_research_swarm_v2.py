from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_edge_focused_research_swarm_v2_emits_edge_source_gap_tasks() -> None:
    report = assert_v20_report("edge_focused_research_swarm_v2_report.json", "tasks")
    categories = {task["category"] for task in report["tasks"]}
    assert {"activate_exchange_native_source", "repair_source_key", "improve_no_trade_gate"} <= categories

