from __future__ import annotations

from typing import Any


class ObserverScaleoutReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.lane_id}:{task.cycle}:{task.source_family}:{task.request_index}")
        if timeout_seconds > 12:
            raise AssertionError("V44 public observer timeout exceeded read-only budget")
        if task.source_family == "weather":
            return {
                "properties": {
                    "temperature": {"value": 23.0 + task.cycle + task.request_index},
                    "timestamp": f"2026-07-05T1{task.cycle}:{task.request_index}0:00Z",
                }
            }
        if task.source_family == "crypto":
            return {
                "data": {"amount": str(64000 + task.cycle * 100 + task.request_index)},
                "timestamp": f"2026-07-05T1{task.cycle}:{task.request_index}5:00Z",
            }
        if task.source_family == "public_event_reference":
            return [{"indicator": {"id": "FP.CPI.TOTL.ZG"}, "value": 3.1 + task.cycle, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


def v44_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from scripts.generate_v44_reports import generate_all_v44_reports_for_tests

    return generate_all_v44_reports_for_tests(**kwargs)


def v44_enabled_reports() -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v44_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=ObserverScaleoutReadOnlyTransport())


def assert_v44_report_named(name: str, key: str | None = None, *, enabled: bool = False) -> dict[str, Any]:
    reports = v44_enabled_reports() if enabled else v44_reports()
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
    assert report["broker_schema_created"] is False
    assert report["order_intent_objects_created"] is False
    assert report["position_sizing_artifacts_created"] is False
    assert report["capital_allocation_artifacts_created"] is False
    assert report["portfolio_construction_artifacts_created"] is False
    assert report["account_balance_private_position_accessed"] is False
    assert report["browser_automation_added"] is False
    assert report["pageagent_added"] is False
    assert report["dom_extraction_added"] is False
    assert report["mined_repo_executed"] is False
    assert report["sports_source_activated"] is False
    assert report["fake_transport_score_claimed_live"] is False
    assert report["duplicate_evidence_scored_as_new"] is False
    assert report["live_trading_readiness_claim"] is False
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report


CURRENT_TEST_REPORTS: dict[str, tuple[str, str]] = {
    "test_exact_gate_runtime_v12": ("exact_gate_runtime_v12_report.json", "exact_gate_runtime_v12_status"),
    "test_v43_baseline_readback_v1": ("v43_baseline_readback_v1_report.json", "v43_baseline_status"),
    "test_observer_lane_isolation_v1": ("observer_lane_isolation_v1_report.json", "observer_lane_isolation_status"),
    "test_source_rotation_engine_v1": ("source_rotation_engine_v1_report.json", "source_rotation_status"),
    "test_observer_evidence_ledger_v1": ("observer_evidence_ledger_v1_report.json", "observer_evidence_ledger_status"),
    "test_observer_settlement_observation_closure_v1": ("observer_settlement_observation_closure_v1_report.json", "observer_settlement_observation_status"),
    "test_observer_real_score_expansion_v1": ("observer_real_score_expansion_v1_report.json", "observer_real_score_expansion_status"),
    "test_observer_sample_diversity_gate_v1": ("observer_sample_diversity_gate_v1_report.json", "sample_diversity_status"),
    "test_calibration_stability_window_v2": ("calibration_stability_window_v2_report.json", "calibration_stability_status"),
    "test_source_truth_v25_observer_stability": ("source_truth_v25_observer_stability_report.json", "source_truth_v25_status"),
    "test_market_class_reliability_v5_observer_delta": ("market_class_reliability_v5_observer_delta_report.json", "market_class_reliability_v5_status"),
    "test_no_trade_discipline_v5_observer_trend": ("no_trade_discipline_v5_observer_trend_report.json", "no_trade_discipline_v5_status"),
    "test_forecast_quality_ledger_v3_observer_trend": ("forecast_quality_ledger_v3_observer_trend_report.json", "forecast_quality_ledger_v3_status"),
    "test_readiness_governor_v4": ("readiness_governor_v4_report.json", "readiness_governor_v4_status"),
    "test_execution_lock_deep_recheck_v3": ("execution_lock_deep_recheck_v3_report.json", "execution_lock_v3_status"),
    "test_completion_oriented_next_action_v44": ("completion_oriented_next_action_v44_report.json", "current_next_action"),
    "test_v44_observer_scaleout_audit_ledger": ("v44_observer_scaleout_audit_ledger_report.json", "v44_observer_scaleout_audit_ledger_status"),
    "test_dashboard_v44": ("dashboard_v44_report_v1.json", "dashboard_status"),
    "test_dummy_mission_state_v44": ("dummy_mission_state_report_v30.json", "mission_state_verdict"),
    "test_v44_runtime_budget": ("v44_runtime_budget_report.json", "v44_runtime_budget_status"),
    "test_v43_still_passes_or_partial_expected_v44": ("v43_still_passes_or_partial_expected_v44_report.json", "v43_still_passes_or_partial_expected_v44_status"),
}


SAFETY_REPORTS = {
    "test_no_secret_leak_v44": "no_secret_leak_report_v44.json",
    "test_no_direct_order_bypass_v44": "no_direct_order_bypass_report_v44.json",
    "test_no_order_ticket_generation_v44": "no_order_ticket_generation_report_v44.json",
    "test_no_shadow_order_generation_v44": "no_shadow_order_generation_report_v44.json",
    "test_no_dry_submit_packet_generation_v44": "no_dry_submit_packet_generation_report_v44.json",
    "test_no_broker_payload_generation_v44": "no_broker_payload_generation_report_v44.json",
    "test_no_execution_rehearsal_v44": "no_execution_rehearsal_report_v44.json",
    "test_no_broker_schema_generation_v44": "no_broker_schema_generation_report_v44.json",
    "test_no_order_intent_object_generation_v44": "no_order_intent_object_generation_report_v44.json",
    "test_no_position_sizing_artifact_v44": "no_position_sizing_artifact_report_v44.json",
    "test_no_capital_allocation_artifact_v44": "no_capital_allocation_artifact_report_v44.json",
    "test_no_portfolio_construction_artifact_v44": "no_portfolio_construction_artifact_report_v44.json",
    "test_no_account_balance_private_position_access_v44": "no_account_balance_private_position_access_report_v44.json",
    "test_no_live_submit_still_disabled_v44": "no_live_submit_still_disabled_report_v44.json",
    "test_no_caps_config_modification_v44": "no_caps_config_modification_report_v44.json",
    "test_no_browser_automation_v44": "no_browser_automation_report_v44.json",
    "test_no_mined_repo_execution_v44": "no_mined_repo_execution_report_v44.json",
    "test_no_fake_transport_score_claimed_live_v44": "no_fake_transport_score_claimed_live_report_v44.json",
    "test_no_missing_ack_probe_run_v44": "no_missing_ack_probe_run_report_v44.json",
    "test_no_fuzzy_ack_probe_run_v44": "no_fuzzy_ack_probe_run_report_v44.json",
    "test_no_sports_source_activation_v44": "no_sports_source_activation_report_v44.json",
    "test_no_duplicate_evidence_scored_as_new_v44": "no_duplicate_evidence_scored_as_new_report_v44.json",
    "test_no_observer_scaleout_controller_to_execution_bridge_v44": "no_observer_scaleout_controller_to_execution_bridge_report_v44.json",
    "test_no_observer_lane_to_execution_bridge_v44": "no_observer_lane_to_execution_bridge_report_v44.json",
    "test_no_source_rotation_to_execution_bridge_v44": "no_source_rotation_to_execution_bridge_report_v44.json",
    "test_no_evidence_ledger_to_execution_bridge_v44": "no_evidence_ledger_to_execution_bridge_report_v44.json",
    "test_no_score_expansion_to_execution_bridge_v44": "no_score_expansion_to_execution_bridge_report_v44.json",
    "test_no_readiness_governor_to_execution_bridge_v44": "no_readiness_governor_to_execution_bridge_report_v44.json",
    "test_no_next_action_to_execution_bridge_v44": "no_next_action_to_execution_bridge_report_v44.json",
}


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    if stem in SAFETY_REPORTS:
        return assert_v44_report_named(SAFETY_REPORTS[stem], "safety_status")
    name, key = CURRENT_TEST_REPORTS[stem]
    return assert_v44_report_named(name, key)
