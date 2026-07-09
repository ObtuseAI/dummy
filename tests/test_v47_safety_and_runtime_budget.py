from __future__ import annotations

from predator_mesh.v47.reports import SAFETY_REPORT_NAMES
from tests.v47_test_helpers import assert_v47_report_named


def test_v47_runtime_budget_report() -> None:
    report = assert_v47_report_named("v47_runtime_budget_report.json", "v47_runtime_budget_status", enabled=True)
    assert report["max_total_requests"] == 36
    assert report["max_requests_per_source_family_per_lane"] == 3
    assert report["per_request_timeout_seconds"] == 12
    assert report["normal_tests_live_network"] is False
    assert report["browser_calls_allowed"] is False


def test_v47_required_safety_reports_are_read_only() -> None:
    for name in SAFETY_REPORT_NAMES:
        report = assert_v47_report_named(name, "safety_status", enabled=True)
        assert report["safety_status"] == "PASS"
        assert report["no_invalid_scoring"] is True


def test_v47_final_report_manifest_contains_required_artifacts() -> None:
    reports = assert_v47_report_named("final_report_v47.json", "all_required_reports_generated", enabled=True)
    assert reports["verdict"] == "PASS"
    assert reports["all_required_reports_generated"] is True
    for required in [
        "dummy_mission_state_report_v33.json",
        "v47_observer_threshold_closure_report.json",
        "source_truth_v28_stable_sample_review_report.json",
        "market_class_reliability_v8_stable_sample_review_report.json",
        "no_trade_discipline_v8_report.json",
        "forecast_quality_ledger_v6_report.json",
        "readiness_governor_v7_report.json",
        "execution_lock_deep_recheck_v6_report.json",
        "dashboard_v47_report_v1.json",
    ]:
        assert required in reports["report_verdicts"]
