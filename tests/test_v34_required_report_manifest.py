from __future__ import annotations

from tests.v34_test_helpers import v34_reports


def test_v34_required_report_manifest_contains_core_reports() -> None:
    reports = v34_reports()
    final = reports["final_report_v34.json"]
    required = {
        "v34_operator_enabled_probe_run_reconciliation_controller_v1_report.json",
        "exact_gate_acknowledgement_hardening_v3_report.json",
        "bounded_readonly_public_probe_pass_v2_report.json",
        "weather_observation_reconciliation_v2_report.json",
        "crypto_price_reconciliation_v2_report.json",
        "public_event_reference_reconciliation_v2_report.json",
        "kalshi_readonly_rule_reconciliation_v2_report.json",
        "live_evidence_reconciliation_ledger_v1_report.json",
        "settlement_join_reconciliation_v4_report.json",
        "due_forecast_closure_reconciliation_v7_report.json",
        "live_score_closure_reconciliation_v5_report.json",
        "live_calibration_reconciliation_v5_report.json",
        "probe_run_artifact_reconciliation_cache_v4_report.json",
        "reconciled_probe_audit_ledger_v3_report.json",
        "sports_probe_exclusion_recheck_v5_report.json",
        "source_truth_probe_reconciliation_v15_report.json",
        "dummy_mission_state_report_v20.json",
        "dashboard_v34_report_v1.json",
        "no_missing_ack_probe_run_report_v34.json",
        "no_fuzzy_ack_probe_run_report_v34.json",
        "no_operator_enabled_probe_run_to_execution_bridge_report_v34.json",
    }

    assert required <= set(reports)
    assert final["required_report_count"] >= 185
    assert final["all_required_reports_generated"] is True
    assert final["gate_state"] == "DISABLED_BY_DEFAULT"
    assert final["probe_run_count"] == 0
    assert final["live_public_evidence_packet_count"] == 0
    assert final["live_scored_count"] == 0
    assert final["live_submit_flag_status"] == "PASS_DISABLED"
    assert final["caps_config_status"] == "PASS_UNCHANGED"


def test_v34_final_report_exposes_required_status_rollup() -> None:
    final = v34_reports()["final_report_v34.json"]

    assert final["verdict"] == "PARTIAL"
    assert final["v17_truth_loop_status"] == "PASS"
    assert final["v33_operator_enabled_probe_observation_status"] == "PASS_PARTIAL_EXPECTED"
    assert final["operator_enabled_probe_run_controller_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["exact_ack_validation_status"] == "FAIL_MISSING_ACK"
    assert final["minimal_live_public_probe_execution_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["mission_state_verdict"] == "PARTIAL"
    assert "operator_enabled_probe_run_reconciliation" in final["proof_paths"]


def test_v34_manifest_has_no_v33_report_names_or_execution_bridge() -> None:
    reports = v34_reports()
    for name, report in reports.items():
        assert report.get("execution_bridge_present") is False
        assert report.get("live_submit_disabled") is True
        assert report.get("caps_unchanged") is True
