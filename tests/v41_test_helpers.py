from __future__ import annotations

from typing import Any


class MultiCycleReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.cycle}:{task.source_family}:{task.request_index}")
        suffix = f"{task.cycle}-{task.request_index}"
        if task.source_family == "weather":
            return {
                "properties": {
                    "temperature": {"value": 20.0 + task.cycle + task.request_index},
                    "timestamp": f"2026-07-04T1{task.cycle}:{task.request_index}0:00Z",
                },
                "source": f"weather-{suffix}",
            }
        if task.source_family == "crypto":
            return {
                "data": {"amount": str(61000 + task.cycle * 100 + task.request_index)},
                "timestamp": f"2026-07-04T1{task.cycle}:{task.request_index}5:00Z",
                "source": f"crypto-{suffix}",
            }
        if task.source_family == "public_event":
            return [{"indicator": {"id": "FP.CPI.TOTL.ZG"}, "value": 3.0 + task.request_index / 10, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


def v41_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v41_reports import generate_all_v41_reports_for_tests

    return generate_all_v41_reports_for_tests(**kwargs)


def v41_enabled_reports() -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v41_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=MultiCycleReadOnlyTransport())


def assert_v41_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v41_reports()
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
        "test_v41_multi_cycle_real_sample_expansion_controller_v1": "v41_multi_cycle_real_sample_expansion_controller_v1_report.json",
        "test_exact_gate_runtime_v9": "exact_gate_runtime_v9_report.json",
        "test_v40_baseline_readback_v1": "v40_baseline_readback_v1_report.json",
        "test_bounded_real_public_probe_expansion_v2": "bounded_real_public_probe_expansion_v2_report.json",
        "test_freshness_and_dedupe_gate_v1": "freshness_and_dedupe_gate_v1_report.json",
        "test_expanded_real_evidence_ledger_v2": "expanded_real_evidence_ledger_v2_report.json",
        "test_settlement_compatibility_expansion_v2": "settlement_compatibility_expansion_v2_report.json",
        "test_due_observation_closure_expansion_v2": "due_observation_closure_expansion_v2_report.json",
        "test_real_live_score_sample_expansion_v2": "real_live_score_sample_expansion_v2_report.json",
        "test_calibration_deepening_v2": "calibration_deepening_v2_report.json",
        "test_source_truth_v22_real_sample_ranking": "source_truth_v22_real_sample_ranking_report.json",
        "test_no_trade_discipline_v2": "no_trade_discipline_v2_report.json",
        "test_market_class_scoreboard_v2": "market_class_scoreboard_v2_report.json",
        "test_readiness_ladder_v1": "readiness_ladder_v1_report.json",
        "test_completion_oriented_next_action_v41": "completion_oriented_next_action_v41_report.json",
        "test_v41_real_sample_audit_ledger": "v41_real_sample_audit_ledger_report.json",
        "test_dashboard_v41": "dashboard_v41_report_v1.json",
        "test_dummy_mission_state_v41": "dummy_mission_state_report_v27.json",
        "test_v41_runtime_budget": "v41_runtime_budget_report.json",
        "test_no_secret_leak_v41": "no_secret_leak_report_v41.json",
        "test_no_direct_order_bypass_v41": "no_direct_order_bypass_report_v41.json",
        "test_no_order_ticket_generation_v41": "no_order_ticket_generation_report_v41.json",
        "test_no_shadow_order_generation_v41": "no_shadow_order_generation_report_v41.json",
        "test_no_dry_submit_packet_generation_v41": "no_dry_submit_packet_generation_report_v41.json",
        "test_no_broker_payload_generation_v41": "no_broker_payload_generation_report_v41.json",
        "test_no_execution_rehearsal_v41": "no_execution_rehearsal_report_v41.json",
        "test_no_live_submit_still_disabled_v41": "no_live_submit_still_disabled_report_v41.json",
        "test_no_caps_config_modification_v41": "no_caps_config_modification_report_v41.json",
        "test_no_browser_automation_v41": "no_browser_automation_report_v41.json",
        "test_no_mined_repo_execution_v41": "no_mined_repo_execution_report_v41.json",
        "test_no_fake_transport_score_claimed_live_v41": "no_fake_transport_score_claimed_live_report_v41.json",
        "test_no_missing_ack_probe_run_v41": "no_missing_ack_probe_run_report_v41.json",
        "test_no_fuzzy_ack_probe_run_v41": "no_fuzzy_ack_probe_run_report_v41.json",
        "test_no_sports_source_activation_v41": "no_sports_source_activation_report_v41.json",
        "test_no_multi_cycle_controller_to_execution_bridge_v41": "no_multi_cycle_controller_to_execution_bridge_report_v41.json",
        "test_no_probe_expansion_to_execution_bridge_v41": "no_probe_expansion_to_execution_bridge_report_v41.json",
        "test_no_live_score_to_execution_bridge_v41": "no_live_score_to_execution_bridge_report_v41.json",
        "test_no_calibration_to_execution_bridge_v41": "no_calibration_to_execution_bridge_report_v41.json",
        "test_no_source_truth_to_execution_bridge_v41": "no_source_truth_to_execution_bridge_report_v41.json",
        "test_no_no_trade_discipline_to_execution_bridge_v41": "no_no_trade_discipline_to_execution_bridge_report_v41.json",
        "test_no_readiness_ladder_to_execution_bridge_v41": "no_readiness_ladder_to_execution_bridge_report_v41.json",
        "test_no_next_action_to_execution_bridge_v41": "no_next_action_to_execution_bridge_report_v41.json",
        "test_v40_still_passes_or_partial_expected_v41": "v40_still_passes_or_partial_expected_v41_report.json",
    }
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    return assert_v41_report_named(candidates[stem])
