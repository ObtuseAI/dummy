from __future__ import annotations

from typing import Any


def v35_reports() -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v35_reports import generate_all_v35_reports_for_tests

    return generate_all_v35_reports_for_tests()


def assert_v35_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v35_reports()
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["execution_bridge_present"] is False
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    candidates = {
        "test_v34_change_review_and_qc_confirmation_v2": "v34_change_review_and_qc_confirmation_v2_report.json",
        "test_v34_dispatch_overlap_fix_check": "v34_dispatch_overlap_fix_check_report.json",
        "test_v34_dead_constant_removal_check": "v34_dead_constant_removal_check_report.json",
        "test_frontend_build_confirmation_v1": "frontend_build_confirmation_v1_report.json",
        "test_v34_default_path_reverification_v1": "v34_default_path_reverification_v1_report.json",
        "test_v34_enabled_path_reverification_v1": "v34_enabled_path_reverification_v1_report.json",
        "test_enabled_path_evidence_mode_audit_v1": "enabled_path_evidence_mode_audit_v1_report.json",
        "test_live_score_sample_expansion_readiness_v1": "live_score_sample_expansion_readiness_v1_report.json",
        "test_live_calibration_low_sample_qc_v1": "live_calibration_low_sample_qc_v1_report.json",
        "test_v34_route_api_smoke_v1": "v34_route_api_smoke_v1_report.json",
        "test_report_transform_consistency_v1": "report_transform_consistency_v1_report.json",
        "test_protected_hash_reverification_v1": "protected_hash_reverification_v1_report.json",
        "test_no_execution_bridge_deep_recheck_v1": "no_execution_bridge_deep_recheck_v1_report.json",
        "test_sports_fixture_only_reverification_v6": "sports_fixture_only_reverification_v6_report.json",
        "test_source_truth_v16_qc_and_sample_readiness": "source_truth_v16_qc_and_sample_readiness_report.json",
        "test_v35_partial_reduction_ledger": "v35_partial_reduction_ledger_report.json",
        "test_v35_sprint_queue_v12": "v35_sprint_queue_v12_report.json",
        "test_v35_compounding_control_plane_v19": "v35_compounding_control_plane_v19_report.json",
        "test_domain_market_class_scoreboard_v20": "domain_market_class_scoreboard_v20_report.json",
        "test_dummy_mission_state_v35": "dummy_mission_state_report_v21.json",
        "test_dashboard_v35": "dashboard_v35_report_v1.json",
        "test_v35_runtime_budget": "v35_runtime_budget_report_v1.json",
        "test_no_secret_leak_v35": "no_secret_leak_report_v35.json",
        "test_no_direct_order_bypass_v35": "no_direct_order_bypass_report_v35.json",
        "test_no_browser_automation_v35": "no_browser_automation_report_v35.json",
        "test_no_fake_transport_score_claimed_live_v35": "no_fake_transport_score_claimed_live_report_v35.json",
        "test_no_qc_lane_to_execution_bridge_v35": "no_qc_lane_to_execution_bridge_report_v35.json",
        "test_no_frontend_dashboard_to_execution_bridge_v35": "no_frontend_dashboard_to_execution_bridge_report_v35.json",
        "test_no_sprint_queue_to_execution_bridge_v35": "no_sprint_queue_to_execution_bridge_report_v35.json",
        "test_v34_still_passes_or_partial_expected_v35": "dummy_mission_state_report_v21.json",
    }
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    return assert_v35_report_named(candidates[stem])


#: Report-level status values meaning "caps configuration is intact".
#:
#: The report vocabulary differs from ``core.caps_authority``'s state strings.
#: An intact-but-unregistered config reports ``REVIEW_REQUIRED``; once an
#: operator issues a valid registration the same reports say ``PASS_REGISTERED``
#: or ``PASS``. Tests that pinned ``REVIEW_REQUIRED`` were asserting the
#: operator had not exercised a sanctioned path, so they turned red the moment
#: they did. Any FAIL/BLOCKED value is excluded, so tamper detection is
#: unchanged.
CAPS_INTACT_REPORT_STATUSES = frozenset({"REVIEW_REQUIRED", "PASS_REGISTERED", "PASS"})
