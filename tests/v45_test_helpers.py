from __future__ import annotations

from typing import Any


class ObserverContinuationReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.lane_id}:{task.cycle}:{task.source_family}:{task.request_index}")
        if timeout_seconds > 12:
            raise AssertionError("V45 public observer timeout exceeded read-only budget")
        if task.source_family == "weather":
            return {
                "properties": {
                    "temperature": {"value": 24.0 + task.cycle + task.request_index},
                    "timestamp": f"2026-07-05T2{task.cycle}:{task.request_index}0:00Z",
                }
            }
        if task.source_family == "crypto":
            return {
                "data": {"amount": str(65000 + task.cycle * 100 + task.request_index)},
                "timestamp": f"2026-07-05T2{task.cycle}:{task.request_index}5:00Z",
            }
        if task.source_family == "public_event_reference":
            return [{"indicator": {"id": "NY.GDP.MKTP.CD"}, "value": 29100000000000 + task.request_index, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


def v45_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v45_reports import generate_all_v45_reports_for_tests

    return generate_all_v45_reports_for_tests(**kwargs)


def v45_enabled_reports() -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v45_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=ObserverContinuationReadOnlyTransport())


def assert_v45_report_named(name: str, key: str | None = None, *, enabled: bool = False) -> dict[str, Any]:
    reports = v45_enabled_reports() if enabled else v45_reports()
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
    assert report["stable_sample_candidate_live_trading_readiness_claim"] is False
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report


CURRENT_TEST_REPORTS: dict[str, tuple[str, str]] = {
    "test_exact_gate_runtime_v13": ("exact_gate_runtime_v13_report.json", "exact_gate_runtime_v13_status"),
    "test_v44_baseline_readback_v1": ("v44_baseline_readback_v1_report.json", "v44_baseline_status"),
    "test_observer_lane_continuation_v1": ("observer_lane_continuation_v1_report.json", "observer_lane_continuation_status"),
    "test_source_portfolio_rotation_v1": ("source_portfolio_rotation_v1_report.json", "source_portfolio_status"),
    "test_observer_evidence_ledger_v2": ("observer_evidence_ledger_v2_report.json", "observer_evidence_ledger_v2_status"),
    "test_observer_settlement_observation_closure_v2": ("observer_settlement_observation_closure_v2_report.json", "observer_settlement_observation_v2_status"),
    "test_observer_real_score_expansion_v2": ("observer_real_score_expansion_v2_report.json", "observer_real_score_expansion_v2_status"),
    "test_sample_diversity_temporal_spread_gate_v2": ("sample_diversity_temporal_spread_gate_v2_report.json", "sample_diversity_status"),
    "test_calibration_stability_drift_window_v3": ("calibration_stability_drift_window_v3_report.json", "calibration_drift_status"),
    "test_source_truth_v26_portfolio_stability": ("source_truth_v26_portfolio_stability_report.json", "source_truth_v26_status"),
    "test_market_class_reliability_v6_portfolio_delta": ("market_class_reliability_v6_portfolio_delta_report.json", "market_class_reliability_v6_status"),
    "test_no_trade_discipline_v6_portfolio_trend": ("no_trade_discipline_v6_portfolio_trend_report.json", "no_trade_discipline_v6_status"),
    "test_forecast_quality_ledger_v4_portfolio_trend": ("forecast_quality_ledger_v4_portfolio_trend_report.json", "forecast_quality_ledger_v4_status"),
    "test_stable_sample_candidate_prep_v1": ("stable_sample_candidate_prep_v1_report.json", "stable_sample_prep_status"),
    "test_readiness_governor_v5": ("readiness_governor_v5_report.json", "readiness_governor_v5_status"),
    "test_execution_lock_deep_recheck_v4": ("execution_lock_deep_recheck_v4_report.json", "execution_lock_v4_status"),
    "test_completion_oriented_next_action_v45": ("completion_oriented_next_action_v45_report.json", "current_next_action"),
    "test_v45_observer_continuation_audit_ledger": ("v45_observer_continuation_audit_ledger_report.json", "v45_observer_continuation_audit_ledger_status"),
    "test_dashboard_v45": ("dashboard_v45_report_v1.json", "dashboard_status"),
    "test_dummy_mission_state_v45": ("dummy_mission_state_report_v31.json", "mission_state_verdict"),
    "test_v45_runtime_budget": ("v45_runtime_budget_report.json", "v45_runtime_budget_status"),
    "test_v44_still_passes_or_partial_expected_v45": ("v44_still_passes_or_partial_expected_v45_report.json", "v44_still_passes_or_partial_expected_v45_status"),
}


SAFETY_REPORTS = {
    "test_no_secret_leak_v45": "no_secret_leak_report_v45.json",
    "test_no_direct_order_bypass_v45": "no_direct_order_bypass_report_v45.json",
    "test_no_order_ticket_generation_v45": "no_order_ticket_generation_report_v45.json",
    "test_no_shadow_order_generation_v45": "no_shadow_order_generation_report_v45.json",
    "test_no_dry_submit_packet_generation_v45": "no_dry_submit_packet_generation_report_v45.json",
    "test_no_broker_payload_generation_v45": "no_broker_payload_generation_report_v45.json",
    "test_no_execution_rehearsal_v45": "no_execution_rehearsal_report_v45.json",
    "test_no_broker_schema_generation_v45": "no_broker_schema_generation_report_v45.json",
    "test_no_order_intent_object_generation_v45": "no_order_intent_object_generation_report_v45.json",
    "test_no_position_sizing_artifact_v45": "no_position_sizing_artifact_report_v45.json",
    "test_no_capital_allocation_artifact_v45": "no_capital_allocation_artifact_report_v45.json",
    "test_no_portfolio_construction_artifact_v45": "no_portfolio_construction_artifact_report_v45.json",
    "test_no_account_balance_private_position_access_v45": "no_account_balance_private_position_access_report_v45.json",
    "test_no_live_submit_still_disabled_v45": "no_live_submit_still_disabled_report_v45.json",
    "test_no_caps_config_modification_v45": "no_caps_config_modification_report_v45.json",
    "test_no_browser_automation_v45": "no_browser_automation_report_v45.json",
    "test_no_mined_repo_execution_v45": "no_mined_repo_execution_report_v45.json",
    "test_no_fake_transport_score_claimed_live_v45": "no_fake_transport_score_claimed_live_report_v45.json",
    "test_no_missing_ack_probe_run_v45": "no_missing_ack_probe_run_report_v45.json",
    "test_no_fuzzy_ack_probe_run_v45": "no_fuzzy_ack_probe_run_report_v45.json",
    "test_no_sports_source_activation_v45": "no_sports_source_activation_report_v45.json",
    "test_no_duplicate_evidence_scored_as_new_v45": "no_duplicate_evidence_scored_as_new_report_v45.json",
    "test_no_observer_continuation_controller_to_execution_bridge_v45": "no_observer_continuation_controller_to_execution_bridge_report_v45.json",
    "test_no_observer_lane_to_execution_bridge_v45": "no_observer_lane_to_execution_bridge_report_v45.json",
    "test_no_source_portfolio_to_execution_bridge_v45": "no_source_portfolio_to_execution_bridge_report_v45.json",
    "test_no_evidence_ledger_to_execution_bridge_v45": "no_evidence_ledger_to_execution_bridge_report_v45.json",
    "test_no_score_expansion_to_execution_bridge_v45": "no_score_expansion_to_execution_bridge_report_v45.json",
    "test_no_stable_sample_prep_to_execution_bridge_v45": "no_stable_sample_prep_to_execution_bridge_report_v45.json",
    "test_no_readiness_governor_to_execution_bridge_v45": "no_readiness_governor_to_execution_bridge_report_v45.json",
    "test_no_next_action_to_execution_bridge_v45": "no_next_action_to_execution_bridge_report_v45.json",
}


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    if stem in SAFETY_REPORTS:
        return assert_v45_report_named(SAFETY_REPORTS[stem], "safety_status")
    name, key = CURRENT_TEST_REPORTS[stem]
    return assert_v45_report_named(name, key)
