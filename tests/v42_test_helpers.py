from __future__ import annotations

from typing import Any


class CalibrationReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.cycle}:{task.source_family}:{task.request_index}")
        if task.source_family == "weather":
            return {
                "properties": {
                    "temperature": {"value": 22.0 + task.cycle + task.request_index},
                    "timestamp": f"2026-07-04T2{task.cycle}:{task.request_index}0:00Z",
                }
            }
        if task.source_family == "crypto":
            return {
                "data": {"amount": str(62000 + task.cycle * 100 + task.request_index)},
                "timestamp": f"2026-07-04T2{task.cycle}:{task.request_index}5:00Z",
            }
        if task.source_family == "public_event":
            return [{"indicator": {"id": "NY.GDP.MKTP.CD"}, "value": 29000000000000 + task.request_index, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


def v42_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v42_reports import generate_all_v42_reports_for_tests

    return generate_all_v42_reports_for_tests(**kwargs)


def v42_enabled_reports() -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v42_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=CalibrationReadOnlyTransport())


def assert_v42_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v42_reports()
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
    assert report["live_trading_readiness_claim"] is False
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    candidates = {
        "test_v42_real_calibration_deepening_controller_v1": "v42_real_calibration_deepening_controller_v1_report.json",
        "test_exact_gate_runtime_v10": "exact_gate_runtime_v10_report.json",
        "test_v41_baseline_readback_v1": "v41_baseline_readback_v1_report.json",
        "test_optional_bounded_sample_extension_v1": "optional_bounded_sample_extension_v1_report.json",
        "test_calibration_sample_quality_gate_v1": "calibration_sample_quality_gate_v1_report.json",
        "test_reliability_calibration_metrics_v1": "reliability_calibration_metrics_v1_report.json",
        "test_calibration_tier_governor_v1": "calibration_tier_governor_v1_report.json",
        "test_source_truth_v23_stability_engine": "source_truth_v23_stability_engine_report.json",
        "test_market_class_reliability_v3": "market_class_reliability_v3_report.json",
        "test_no_trade_discipline_v3": "no_trade_discipline_v3_report.json",
        "test_forecast_quality_ledger_v1": "forecast_quality_ledger_v1_report.json",
        "test_readiness_governor_v2": "readiness_governor_v2_report.json",
        "test_execution_lock_deep_recheck_v1": "execution_lock_deep_recheck_v1_report.json",
        "test_completion_oriented_next_action_v42": "completion_oriented_next_action_v42_report.json",
        "test_v42_calibration_audit_ledger": "v42_calibration_audit_ledger_report.json",
        "test_dashboard_v42": "dashboard_v42_report_v1.json",
        "test_dummy_mission_state_v42": "dummy_mission_state_report_v28.json",
        "test_v42_runtime_budget": "v42_runtime_budget_report.json",
        "test_no_secret_leak_v42": "no_secret_leak_report_v42.json",
        "test_no_direct_order_bypass_v42": "no_direct_order_bypass_report_v42.json",
        "test_no_order_ticket_generation_v42": "no_order_ticket_generation_report_v42.json",
        "test_no_shadow_order_generation_v42": "no_shadow_order_generation_report_v42.json",
        "test_no_dry_submit_packet_generation_v42": "no_dry_submit_packet_generation_report_v42.json",
        "test_no_broker_payload_generation_v42": "no_broker_payload_generation_report_v42.json",
        "test_no_execution_rehearsal_v42": "no_execution_rehearsal_report_v42.json",
        "test_no_live_submit_still_disabled_v42": "no_live_submit_still_disabled_report_v42.json",
        "test_no_caps_config_modification_v42": "no_caps_config_modification_report_v42.json",
        "test_no_browser_automation_v42": "no_browser_automation_report_v42.json",
        "test_no_mined_repo_execution_v42": "no_mined_repo_execution_report_v42.json",
        "test_no_fake_transport_score_claimed_live_v42": "no_fake_transport_score_claimed_live_report_v42.json",
        "test_no_missing_ack_probe_run_v42": "no_missing_ack_probe_run_report_v42.json",
        "test_no_fuzzy_ack_probe_run_v42": "no_fuzzy_ack_probe_run_report_v42.json",
        "test_no_sports_source_activation_v42": "no_sports_source_activation_report_v42.json",
        "test_no_duplicate_evidence_scored_as_new_v42": "no_duplicate_evidence_scored_as_new_report_v42.json",
        "test_no_calibration_controller_to_execution_bridge_v42": "no_calibration_controller_to_execution_bridge_report_v42.json",
        "test_no_sample_extension_to_execution_bridge_v42": "no_sample_extension_to_execution_bridge_report_v42.json",
        "test_no_calibration_metrics_to_execution_bridge_v42": "no_calibration_metrics_to_execution_bridge_report_v42.json",
        "test_no_source_truth_to_execution_bridge_v42": "no_source_truth_to_execution_bridge_report_v42.json",
        "test_no_readiness_governor_to_execution_bridge_v42": "no_readiness_governor_to_execution_bridge_report_v42.json",
        "test_no_next_action_to_execution_bridge_v42": "no_next_action_to_execution_bridge_report_v42.json",
        "test_v41_still_passes_or_partial_expected_v42": "v41_still_passes_or_partial_expected_v42_report.json",
    }
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    return assert_v42_report_named(candidates[stem])
