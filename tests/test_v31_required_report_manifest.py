from __future__ import annotations

from tests.v31_test_helpers import v31_reports


def test_v31_required_report_manifest_contains_core_reports() -> None:
    reports = v31_reports()
    final = reports["final_report_v31.json"]

    required = {
        "explicit_public_probe_operator_gate_v3_report.json",
        "v30_adapter_public_probe_runner_v1_report.json",
        "live_public_evidence_capture_v1_report.json",
        "weather_public_probe_implementation_v2_report.json",
        "crypto_public_probe_implementation_v2_report.json",
        "public_event_reference_probe_implementation_v2_report.json",
        "kalshi_readonly_rule_probe_implementation_v2_report.json",
        "probe_evidence_normalization_pipeline_v2_report.json",
        "due_forecast_live_observation_closure_v4_report.json",
        "live_score_seed_v2_report.json",
        "live_calibration_seed_v2_report.json",
        "public_probe_cache_writer_v1_report.json",
        "probe_run_audit_ledger_v1_report.json",
        "sports_fixture_guard_recheck_v2_report.json",
        "probe_source_truth_v12_report.json",
        "dummy_mission_state_report_v17.json",
        "dashboard_v31_report_v1.json",
        "no_public_probe_gate_to_execution_bridge_report_v31.json",
        "no_public_probe_failure_scored_live_report_v31.json",
    }

    assert required <= set(reports)
    assert final["required_report_count"] >= 130
    assert final["all_required_reports_generated"] is True
    assert final["public_probe_gate_state"] == "DISABLED_BY_DEFAULT"
    assert final["probe_run_count"] == 0
    assert final["live_public_evidence_packet_count"] == 0
    assert final["live_scored_count"] == 0
    assert final["live_submit_flag_status"] == "PASS_DISABLED"
    assert final["caps_config_status"] == "PASS_UNCHANGED"


def test_v31_final_report_exposes_required_status_rollup() -> None:
    final = v31_reports()["final_report_v31.json"]

    assert final["verdict"] == "PARTIAL"
    assert final["v17_truth_loop_status"] == "PASS"
    assert final["v21_source_activation_status"] == "PASS"
    assert final["v22_forecast_write_status"] == "PASS"
    assert final["v30_in_house_adapter_implementation_status"] == "PASS_PARTIAL_EXPECTED"
    assert final["public_probe_operator_gate_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["public_probe_runner_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["due_forecast_observation_closure_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["mission_state_verdict"] == "PARTIAL"
    assert "public_probe_gate" in final["proof_paths"]
