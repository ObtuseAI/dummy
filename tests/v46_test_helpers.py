from __future__ import annotations

from typing import Any


class ThresholdPursuitReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.lane_id}:{task.cycle}:{task.source_family}:{task.request_index}")
        if timeout_seconds > 12:
            raise AssertionError("V46 public observer timeout exceeded read-only budget")
        if task.source_family == "weather":
            return {
                "properties": {
                    "temperature": {"value": 25.0 + task.cycle + task.request_index},
                    "timestamp": f"2026-07-05T1{task.cycle}:{task.request_index}0:00Z",
                }
            }
        if task.source_family == "crypto":
            return {
                "data": {"amount": str(66000 + task.cycle * 100 + task.request_index)},
                "timestamp": f"2026-07-05T1{task.cycle}:{task.request_index}5:00Z",
            }
        if task.source_family == "public_event_reference":
            return [{"indicator": {"id": "NY.GDP.MKTP.CD"}, "value": 29200000000000 + task.request_index, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


def v46_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v46_reports import generate_all_v46_reports_for_tests

    return generate_all_v46_reports_for_tests(**kwargs)


def v46_enabled_reports() -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v46_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=ThresholdPursuitReadOnlyTransport())


def assert_v46_report_named(name: str, key: str | None = None, *, enabled: bool = False) -> dict[str, Any]:
    reports = v46_enabled_reports() if enabled else v46_reports()
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
    assert report["mined_repo_executed"] is False
    assert report["sports_source_activated"] is False
    assert report["fake_transport_score_claimed_live"] is False
    assert report["duplicate_evidence_scored_as_new"] is False
    assert report["metric_cluster_inflation_scored_as_new"] is False
    assert report["live_trading_readiness_claim"] is False
    assert report["stable_sample_candidate_live_trading_readiness_claim"] is False
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report


CURRENT_TEST_REPORTS: dict[str, tuple[str, str]] = {
    "test_exact_gate_runtime_v14": ("exact_gate_runtime_v14_report.json", "exact_gate_runtime_v14_status"),
    "test_v45_baseline_readback_v1": ("v45_baseline_readback_v1_report.json", "v45_baseline_status"),
    "test_observer_lane_health_v2": ("observer_lane_health_v2_report.json", "observer_lane_health_v2_status"),
    "test_source_portfolio_rotation_v2": ("source_portfolio_rotation_v2_report.json", "source_portfolio_status"),
    "test_observer_evidence_ledger_v3": ("observer_evidence_ledger_v3_report.json", "observer_evidence_ledger_v3_status"),
    "test_observer_settlement_observation_closure_v3": ("observer_settlement_observation_closure_v3_report.json", "observer_settlement_observation_v3_status"),
    "test_observer_real_score_expansion_v3": ("observer_real_score_expansion_v3_report.json", "observer_real_score_expansion_v3_status"),
    "test_diversity_temporal_concentration_gate_v3": ("diversity_temporal_concentration_gate_v3_report.json", "diversity_temporal_concentration_gate_v3_status"),
    "test_calibration_drift_resilience_window_v4": ("calibration_drift_resilience_window_v4_report.json", "calibration_drift_status"),
    "test_source_truth_v27_drift_resilience": ("source_truth_v27_drift_resilience_report.json", "source_truth_v27_status"),
    "test_market_class_reliability_v7_drift_delta": ("market_class_reliability_v7_drift_delta_report.json", "market_class_reliability_v7_status"),
    "test_no_trade_discipline_v7_drift_trend": ("no_trade_discipline_v7_drift_trend_report.json", "no_trade_discipline_v7_status"),
    "test_forecast_quality_ledger_v5_drift_trend": ("forecast_quality_ledger_v5_drift_trend_report.json", "forecast_quality_ledger_v5_status"),
    "test_stable_sample_gap_analysis_v1": ("stable_sample_gap_analysis_v1_report.json", "stable_sample_gap_status"),
    "test_readiness_governor_v6": ("readiness_governor_v6_report.json", "readiness_governor_v6_status"),
    "test_execution_lock_deep_recheck_v5": ("execution_lock_deep_recheck_v5_report.json", "execution_lock_v5_status"),
    "test_completion_oriented_next_action_v46": ("completion_oriented_next_action_v46_report.json", "current_next_action"),
    "test_v46_threshold_pursuit_audit_ledger": ("v46_threshold_pursuit_audit_ledger_report.json", "v46_threshold_pursuit_audit_ledger_status"),
    "test_dashboard_v46": ("dashboard_v46_report_v1.json", "dashboard_status"),
    "test_dummy_mission_state_v46": ("dummy_mission_state_report_v32.json", "mission_state_verdict"),
    "test_v46_runtime_budget": ("v46_runtime_budget_report.json", "v46_runtime_budget_status"),
    "test_v45_still_passes_or_partial_expected_v46": ("v45_still_passes_or_partial_expected_v46_report.json", "v45_still_passes_or_partial_expected_v46_status"),
}


SAFETY_REPORTS = {
    "test_no_secret_leak_v46": "no_secret_leak_report_v46.json",
    "test_no_direct_order_bypass_v46": "no_direct_order_bypass_report_v46.json",
    "test_no_order_ticket_generation_v46": "no_order_ticket_generation_report_v46.json",
    "test_no_shadow_order_generation_v46": "no_shadow_order_generation_report_v46.json",
    "test_no_dry_submit_packet_generation_v46": "no_dry_submit_packet_generation_report_v46.json",
    "test_no_broker_payload_generation_v46": "no_broker_payload_generation_report_v46.json",
    "test_no_execution_rehearsal_v46": "no_execution_rehearsal_report_v46.json",
    "test_no_broker_schema_generation_v46": "no_broker_schema_generation_report_v46.json",
    "test_no_order_intent_object_generation_v46": "no_order_intent_object_generation_report_v46.json",
    "test_no_position_sizing_artifact_v46": "no_position_sizing_artifact_report_v46.json",
    "test_no_capital_allocation_artifact_v46": "no_capital_allocation_artifact_report_v46.json",
    "test_no_portfolio_construction_artifact_v46": "no_portfolio_construction_artifact_report_v46.json",
    "test_no_account_balance_private_position_access_v46": "no_account_balance_private_position_access_report_v46.json",
    "test_no_live_submit_still_disabled_v46": "no_live_submit_still_disabled_report_v46.json",
    "test_no_caps_config_modification_v46": "no_caps_config_modification_report_v46.json",
    "test_no_browser_automation_v46": "no_browser_automation_report_v46.json",
    "test_no_mined_repo_execution_v46": "no_mined_repo_execution_report_v46.json",
    "test_no_fake_transport_score_claimed_live_v46": "no_fake_transport_score_claimed_live_report_v46.json",
    "test_no_missing_ack_probe_run_v46": "no_missing_ack_probe_run_report_v46.json",
    "test_no_fuzzy_ack_probe_run_v46": "no_fuzzy_ack_probe_run_report_v46.json",
    "test_no_sports_source_activation_v46": "no_sports_source_activation_report_v46.json",
    "test_no_duplicate_evidence_scored_as_new_v46": "no_duplicate_evidence_scored_as_new_report_v46.json",
    "test_no_metric_cluster_inflation_scored_as_new_v46": "no_metric_cluster_inflation_scored_as_new_report_v46.json",
    "test_no_threshold_pursuit_controller_to_execution_bridge_v46": "no_threshold_pursuit_controller_to_execution_bridge_report_v46.json",
    "test_no_observer_lane_to_execution_bridge_v46": "no_observer_lane_to_execution_bridge_report_v46.json",
    "test_no_source_portfolio_to_execution_bridge_v46": "no_source_portfolio_to_execution_bridge_report_v46.json",
    "test_no_evidence_ledger_to_execution_bridge_v46": "no_evidence_ledger_to_execution_bridge_report_v46.json",
    "test_no_score_expansion_to_execution_bridge_v46": "no_score_expansion_to_execution_bridge_report_v46.json",
    "test_no_stable_sample_gap_to_execution_bridge_v46": "no_stable_sample_gap_to_execution_bridge_report_v46.json",
    "test_no_readiness_governor_to_execution_bridge_v46": "no_readiness_governor_to_execution_bridge_report_v46.json",
    "test_no_next_action_to_execution_bridge_v46": "no_next_action_to_execution_bridge_report_v46.json",
}


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    if stem in SAFETY_REPORTS:
        return assert_v46_report_named(SAFETY_REPORTS[stem], "safety_status")
    name, key = CURRENT_TEST_REPORTS[stem]
    return assert_v46_report_named(name, key)
