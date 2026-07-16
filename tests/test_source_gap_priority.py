from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_gap_priority_orders_expected_edge_impact() -> None:
    report = assert_v20_report("source_gap_priority_report_v1.json", "priorities")
    impacts = [item["expected_edge_impact"] for item in report["priorities"]]
    assert impacts == sorted(impacts, reverse=True)
