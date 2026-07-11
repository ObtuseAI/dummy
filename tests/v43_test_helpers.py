from __future__ import annotations

from typing import Any


class DevelopingReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.cycle}:{task.source_family}:{task.request_index}")
        if timeout_seconds > 12:
            raise AssertionError("V43 public probe timeout exceeded read-only budget")
        if task.source_family == "weather":
            return {
                "properties": {
                    "temperature": {"value": 20.0 + task.cycle + task.request_index},
                    "timestamp": f"2026-07-04T3{task.cycle}:{task.request_index}0:00Z",
                }
            }
        if task.source_family == "crypto":
            return {
                "data": {"amount": str(63000 + task.cycle * 100 + task.request_index)},
                "timestamp": f"2026-07-04T3{task.cycle}:{task.request_index}5:00Z",
            }
        if task.source_family == "public_event":
            return [{"indicator": {"id": "FP.CPI.TOTL.ZG"}, "value": 3.0 + task.cycle, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


def v43_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v43_reports import generate_all_v43_reports_for_tests

    return generate_all_v43_reports_for_tests(**kwargs)


def v43_enabled_reports() -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v43_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=DevelopingReadOnlyTransport())


def assert_v43_report_named(name: str, key: str | None = None, *, enabled: bool = False) -> dict[str, Any]:
    reports = v43_enabled_reports() if enabled else v43_reports()
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["execution_bridge_present"] is False
    assert report["order_endpoints_used"] is False
    assert report["cancel_endpoints_used"] is False
    assert report["order_tickets_created"] is False
    assert report["shadow_orders_created"] is False
    assert report["dry_submit_packets_created"] is False
    assert report["broker_payloads_created"] is False
    assert report["execution_rehearsal_created"] is False
    assert report["browser_automation_added"] is False
    assert report["mined_repo_executed"] is False
    assert report["sports_source_activated"] is False
    assert report["live_trading_readiness_claim"] is False
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    candidates = {
        "test_exact_gate_runtime_v11": ("exact_gate_runtime_v11_report.json", "exact_gate_runtime_v11_status"),
        "test_v42_baseline_readback_v1": ("v42_baseline_readback_v1_report.json", "v42_baseline_status"),
        "test_optional_developing_sample_extension_v1": ("optional_developing_sample_extension_v1_report.json", "optional_developing_sample_extension_status"),
        "test_v43_sample_quality_gate_v2": ("v43_sample_quality_gate_v2_report.json", "sample_quality_status"),
        "test_developing_sample_tier_governor_v1": ("developing_sample_tier_governor_v1_report.json", "developing_sample_threshold_decision"),
        "test_calibration_stability_window_v1": ("calibration_stability_window_v1_report.json", "calibration_stability_status"),
        "test_source_truth_v24_stability_window": ("source_truth_v24_stability_window_report.json", "source_truth_v24_status"),
        "test_market_class_reliability_v4_delta": ("market_class_reliability_v4_delta_report.json", "market_class_reliability_v4_status"),
        "test_no_trade_discipline_v4_trend_engine": ("no_trade_discipline_v4_trend_engine_report.json", "no_trade_discipline_v4_status"),
        "test_forecast_quality_ledger_v2_trend_engine": ("forecast_quality_ledger_v2_trend_engine_report.json", "forecast_quality_ledger_v2_status"),
        "test_readonly_observer_scaleout_plan_v1": ("readonly_observer_scaleout_plan_v1_report.json", "observer_scaleout_plan_status"),
        "test_readiness_governor_v3": ("readiness_governor_v3_report.json", "readiness_governor_v3_status"),
        "test_execution_lock_deep_recheck_v2": ("execution_lock_deep_recheck_v2_report.json", "execution_lock_v2_status"),
        "test_completion_oriented_next_action_v43": ("completion_oriented_next_action_v43_report.json", "current_next_action"),
        "test_v43_developing_sample_audit_ledger": ("v43_developing_sample_audit_ledger_report.json", "v43_developing_sample_audit_ledger_status"),
        "test_dashboard_v43": ("dashboard_v43_report_v1.json", "dashboard_status"),
        "test_dummy_mission_state_v43": ("dummy_mission_state_report_v29.json", "mission_state_verdict"),
        "test_v43_runtime_budget": ("v43_runtime_budget_report.json", "v43_runtime_budget_status"),
        "test_no_secret_leak_v43": ("no_secret_leak_report_v43.json", "safety_status"),
        "test_no_direct_order_bypass_v43": ("no_direct_order_bypass_report_v43.json", "safety_status"),
        "test_no_order_ticket_generation_v43": ("no_order_ticket_generation_report_v43.json", "safety_status"),
        "test_no_shadow_order_generation_v43": ("no_shadow_order_generation_report_v43.json", "safety_status"),
        "test_no_dry_submit_packet_generation_v43": ("no_dry_submit_packet_generation_report_v43.json", "safety_status"),
        "test_no_broker_payload_generation_v43": ("no_broker_payload_generation_report_v43.json", "safety_status"),
        "test_no_execution_rehearsal_v43": ("no_execution_rehearsal_report_v43.json", "safety_status"),
        "test_no_broker_schema_generation_v43": ("no_broker_schema_generation_report_v43.json", "safety_status"),
        "test_no_order_intent_object_generation_v43": ("no_order_intent_object_generation_report_v43.json", "safety_status"),
        "test_no_position_sizing_artifact_v43": ("no_position_sizing_artifact_report_v43.json", "safety_status"),
        "test_no_capital_allocation_artifact_v43": ("no_capital_allocation_artifact_report_v43.json", "safety_status"),
        "test_no_live_submit_still_disabled_v43": ("no_live_submit_still_disabled_report_v43.json", "safety_status"),
        "test_no_caps_config_modification_v43": ("no_caps_config_modification_report_v43.json", "safety_status"),
        "test_no_browser_automation_v43": ("no_browser_automation_report_v43.json", "safety_status"),
        "test_no_mined_repo_execution_v43": ("no_mined_repo_execution_report_v43.json", "safety_status"),
        "test_no_fake_transport_score_claimed_live_v43": ("no_fake_transport_score_claimed_live_report_v43.json", "safety_status"),
        "test_no_missing_ack_probe_run_v43": ("no_missing_ack_probe_run_report_v43.json", "safety_status"),
        "test_no_fuzzy_ack_probe_run_v43": ("no_fuzzy_ack_probe_run_report_v43.json", "safety_status"),
        "test_no_sports_source_activation_v43": ("no_sports_source_activation_report_v43.json", "safety_status"),
        "test_no_duplicate_evidence_scored_as_new_v43": ("no_duplicate_evidence_scored_as_new_report_v43.json", "safety_status"),
        "test_no_developing_sample_controller_to_execution_bridge_v43": ("no_developing_sample_controller_to_execution_bridge_report_v43.json", "safety_status"),
        "test_no_sample_extension_to_execution_bridge_v43": ("no_sample_extension_to_execution_bridge_report_v43.json", "safety_status"),
        "test_no_tier_governor_to_execution_bridge_v43": ("no_tier_governor_to_execution_bridge_report_v43.json", "safety_status"),
        "test_no_calibration_stability_to_execution_bridge_v43": ("no_calibration_stability_to_execution_bridge_report_v43.json", "safety_status"),
        "test_no_source_truth_to_execution_bridge_v43": ("no_source_truth_to_execution_bridge_report_v43.json", "safety_status"),
        "test_no_readiness_governor_to_execution_bridge_v43": ("no_readiness_governor_to_execution_bridge_report_v43.json", "safety_status"),
        "test_no_observer_scaleout_to_execution_bridge_v43": ("no_observer_scaleout_to_execution_bridge_report_v43.json", "safety_status"),
        "test_no_next_action_to_execution_bridge_v43": ("no_next_action_to_execution_bridge_report_v43.json", "safety_status"),
        "test_v42_still_passes_or_partial_expected_v43": ("v42_still_passes_or_partial_expected_v43_report.json", "v42_still_passes_or_partial_expected_v43_status"),
    }
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    name, key = candidates[stem]
    return assert_v43_report_named(name, key)
