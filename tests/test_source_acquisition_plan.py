from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_acquisition_plan_does_not_force_purchase() -> None:
    report = assert_v20_report("source_acquisition_plan_report_v1.json", "plans")
    assert report["forced_purchase_recommendations"] is False
    assert all(plan["forced_purchase"] is False for plan in report["plans"])
