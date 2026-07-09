from __future__ import annotations

from tests.v32_test_helpers import v32_reports


def test_v32_required_report_manifest_contains_core_reports() -> None:
    reports = v32_reports()
    final = reports["final_report_v32.json"]
    required = {
        "v32_source_recovery_controller_v1_report.json",
        "operator_gated_probe_run_v2_report.json",
        "minimal_public_probe_pass_v1_report.json",
        "weather_source_recovery_v2_report.json",
        "crypto_source_recovery_v2_report.json",
        "public_event_source_recovery_v2_report.json",
        "kalshi_readonly_source_recovery_v2_report.json",
        "live_public_evidence_expansion_v2_report.json",
        "settlement_compatible_evidence_expansion_v2_report.json",
        "due_forecast_closure_expansion_v5_report.json",
        "live_score_expansion_seed_v3_report.json",
        "live_calibration_expansion_v3_report.json",
        "probe_cache_replay_separation_v2_report.json",
        "sports_fixture_guard_v3_report.json",
        "source_truth_recovery_closure_v13_report.json",
        "dummy_mission_state_report_v18.json",
        "dashboard_v32_report_v1.json",
        "no_source_recovery_to_execution_bridge_report_v32.json",
        "no_disabled_probe_scored_live_report_v32.json",
    }

    assert required <= set(reports)
    assert final["required_report_count"] >= 175
    assert final["all_required_reports_generated"] is True
    assert final["gate_state"] == "DISABLED_BY_DEFAULT"
    assert final["probe_run_count"] == 0
    assert final["live_public_evidence_packet_count"] == 0
    assert final["live_scored_count"] == 0
    assert final["live_submit_flag_status"] == "PASS_DISABLED"
    assert final["caps_config_status"] == "PASS_UNCHANGED"


def test_v32_final_report_exposes_required_status_rollup() -> None:
    final = v32_reports()["final_report_v32.json"]

    assert final["verdict"] == "PARTIAL"
    assert final["v17_truth_loop_status"] == "PASS"
    assert final["v31_public_probe_execution_status"] == "PASS_PARTIAL_EXPECTED"
    assert final["source_recovery_controller_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["operator_gated_probe_run_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["minimal_public_probe_pass_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert final["mission_state_verdict"] == "PARTIAL"
    assert "source_recovery" in final["proof_paths"]
