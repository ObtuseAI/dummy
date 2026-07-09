from __future__ import annotations

from tests.v33_test_helpers import v33_reports


def test_v33_required_report_manifest_contains_core_reports() -> None:
    reports = v33_reports()
    final = reports["final_report_v33.json"]
    required = {
        "v33_operator_enabled_probe_run_controller_v1_report.json",
        "exact_gate_acknowledgement_hardening_v3_report.json",
        "minimal_live_public_probe_execution_v1_report.json",
        "weather_enabled_probe_run_v1_report.json",
        "crypto_enabled_probe_run_v1_report.json",
        "public_event_enabled_probe_run_v1_report.json",
        "kalshi_readonly_enabled_probe_run_v1_report.json",
        "live_public_evidence_ingestion_v3_report.json",
        "settlement_evidence_join_v3_report.json",
        "due_forecast_observation_run_v6_report.json",
        "live_score_observation_run_v4_report.json",
        "live_calibration_observation_run_v4_report.json",
        "public_probe_artifact_cache_v3_report.json",
        "enabled_probe_audit_ledger_v2_report.json",
        "sports_probe_exclusion_guard_v4_report.json",
        "source_truth_enabled_probe_evidence_v14_report.json",
        "dummy_mission_state_report_v19.json",
        "dashboard_v33_report_v1.json",
        "no_missing_ack_probe_run_report_v33.json",
        "no_fuzzy_ack_probe_run_report_v33.json",
        "no_operator_enabled_probe_run_to_execution_bridge_report_v33.json",
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


def test_v33_final_report_exposes_required_status_rollup() -> None:
    final = v33_reports()["final_report_v33.json"]

    assert final["verdict"] == "PARTIAL"
    assert final["v17_truth_loop_status"] == "PASS"
    assert final["v32_source_recovery_live_observation_status"] == "PASS_PARTIAL_EXPECTED"
    assert final["operator_enabled_probe_run_controller_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["exact_ack_validation_status"] == "FAIL_MISSING_ACK"
    assert final["minimal_live_public_probe_execution_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["mission_state_verdict"] == "PARTIAL"
    assert "operator_enabled_probe_run" in final["proof_paths"]
