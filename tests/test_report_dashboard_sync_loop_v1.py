from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_report_dashboard_sync_loop_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["report_dashboard_sync_status"] == "PASS"
    assert report["final_report_contains_latest_version"] is True
    assert report["tests_summary_contains_v37"] is True
    assert report["route_smoke_failures_escalate_to_fail"] is True
    assert report["frontend_build_failures_escalate_to_fail"] is True
