from __future__ import annotations

from typing import Any


class ExpandedReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(task.source_family)
        if task.source_family == "weather":
            return {"properties": {"temperature": {"value": 23.1}, "timestamp": "2026-07-04T13:00:00Z"}}
        if task.source_family == "crypto":
            return {"data": {"amount": "61321.45"}, "timestamp": "2026-07-04T13:00:00Z"}
        if task.source_family == "public_event":
            return [{"indicator": {"id": "FP.CPI.TOTL.ZG"}, "value": 3.1, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


def v40_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v40_reports import generate_all_v40_reports_for_tests

    return generate_all_v40_reports_for_tests(**kwargs)


def v40_enabled_reports() -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v40_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=ExpandedReadOnlyTransport())


def assert_v40_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v40_reports()
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["execution_bridge_present"] is False
    assert report["order_endpoints_used"] is False
    assert report["cancel_endpoints_used"] is False
    assert report["browser_automation_added"] is False
    assert report["mined_repo_executed"] is False
    assert report["sports_source_activated"] is False
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    candidates = {
        "test_v40_real_score_sample_expansion_controller_v1": "v40_real_score_sample_expansion_controller_v1_report.json",
        "test_exact_gate_runtime_v8": "exact_gate_runtime_v8_report.json",
        "test_v39_baseline_readback_v1": "v39_baseline_readback_v1_report.json",
        "test_real_public_probe_expansion_v1": "real_public_probe_expansion_v1_report.json",
        "test_expanded_live_public_evidence_ledger_v1": "expanded_live_public_evidence_ledger_v1_report.json",
        "test_expanded_settlement_join_v1": "expanded_settlement_join_v1_report.json",
        "test_expanded_due_observation_closure_v1": "expanded_due_observation_closure_v1_report.json",
        "test_expanded_real_live_score_sample_v1": "expanded_real_live_score_sample_v1_report.json",
        "test_real_calibration_sample_growth_v1": "real_calibration_sample_growth_v1_report.json",
        "test_source_truth_v21_real_sample_growth": "source_truth_v21_real_sample_growth_report.json",
        "test_no_trade_discipline_real_sample_v1": "no_trade_discipline_real_sample_v1_report.json",
        "test_market_class_real_sample_scoreboard_v1": "market_class_real_sample_scoreboard_v1_report.json",
        "test_completion_oriented_next_action_v40": "completion_oriented_next_action_v40_report.json",
        "test_v40_real_sample_audit_ledger": "v40_real_sample_audit_ledger_report.json",
        "test_dashboard_v40": "dashboard_v40_report_v1.json",
        "test_dummy_mission_state_v40": "dummy_mission_state_report_v26.json",
        "test_v40_runtime_budget": "v40_runtime_budget_report.json",
        "test_no_secret_leak_v40": "no_secret_leak_report_v40.json",
        "test_no_direct_order_bypass_v40": "no_direct_order_bypass_report_v40.json",
        "test_no_live_submit_still_disabled_v40": "no_live_submit_still_disabled_report_v40.json",
        "test_no_caps_config_modification_v40": "no_caps_config_modification_report_v40.json",
        "test_no_browser_automation_v40": "no_browser_automation_report_v40.json",
        "test_no_mined_repo_execution_v40": "no_mined_repo_execution_report_v40.json",
        "test_no_fake_transport_score_claimed_live_v40": "no_fake_transport_score_claimed_live_report_v40.json",
        "test_no_missing_ack_probe_run_v40": "no_missing_ack_probe_run_report_v40.json",
        "test_no_fuzzy_ack_probe_run_v40": "no_fuzzy_ack_probe_run_report_v40.json",
        "test_no_sports_source_activation_v40": "no_sports_source_activation_report_v40.json",
        "test_no_sample_expansion_controller_to_execution_bridge_v40": "no_sample_expansion_controller_to_execution_bridge_report_v40.json",
        "test_no_live_score_to_execution_bridge_v40": "no_live_score_to_execution_bridge_report_v40.json",
        "test_no_next_action_to_execution_bridge_v40": "no_next_action_to_execution_bridge_report_v40.json",
        "test_v39_still_passes_or_partial_expected_v40": "v39_still_passes_or_partial_expected_v40_report.json",
    }
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    return assert_v40_report_named(candidates[stem])
