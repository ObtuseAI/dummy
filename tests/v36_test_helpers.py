from __future__ import annotations

from typing import Any


def v36_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v36_reports import generate_all_v36_reports_for_tests

    kwargs.setdefault("env", {})
    return generate_all_v36_reports_for_tests(**kwargs)


def assert_v36_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v36_reports()
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["execution_bridge_present"] is False
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    candidates = {
        "test_v36_real_probe_run_controller_v1": "v36_real_probe_run_controller_v1_report.json",
        "test_exact_operator_gate_runtime_v5": "exact_operator_gate_runtime_v5_report.json",
        "test_real_readonly_probe_transport_v1": "real_readonly_probe_transport_v1_report.json",
        "test_minimal_real_public_probe_pass_v1": "minimal_real_public_probe_pass_v1_report.json",
        "test_weather_real_public_probe_v1": "weather_real_public_probe_v1_report.json",
        "test_crypto_real_public_probe_v1": "crypto_real_public_probe_v1_report.json",
        "test_public_event_real_public_probe_v1": "public_event_real_public_probe_v1_report.json",
        "test_kalshi_readonly_real_probe_v1": "kalshi_readonly_real_probe_v1_report.json",
        "test_real_live_public_evidence_ledger_v1": "real_live_public_evidence_ledger_v1_report.json",
        "test_real_settlement_join_v1": "real_settlement_join_v1_report.json",
        "test_real_due_forecast_observation_closure_v1": "real_due_forecast_observation_closure_v1_report.json",
        "test_real_live_score_seed_v1": "real_live_score_seed_v1_report.json",
        "test_real_live_calibration_seed_v1": "real_live_calibration_seed_v1_report.json",
        "test_real_probe_artifact_cache_v1": "real_probe_artifact_cache_v1_report.json",
        "test_real_probe_audit_ledger_v1": "real_probe_audit_ledger_v1_report.json",
        "test_fake_to_real_evidence_separation_v1": "fake_to_real_evidence_separation_v1_report.json",
        "test_sports_fixture_only_real_probe_recheck_v7": "sports_fixture_only_real_probe_recheck_v7_report.json",
        "test_source_truth_v17_real_probe_and_sample_readiness": "source_truth_v17_real_probe_and_sample_readiness_report.json",
        "test_v36_partial_reduction_ledger": "v36_partial_reduction_ledger_report.json",
        "test_v36_real_probe_sprint_queue_v13": "v36_real_probe_sprint_queue_v13_report.json",
        "test_v36_compounding_control_plane_v20": "v36_compounding_control_plane_v20_report.json",
        "test_domain_market_class_scoreboard_v21": "domain_market_class_scoreboard_v21_report.json",
        "test_dummy_mission_state_v36": "dummy_mission_state_report_v22.json",
        "test_dashboard_v36": "dashboard_v36_report_v1.json",
        "test_v36_runtime_budget": "v36_runtime_budget_report_v1.json",
        "test_no_secret_leak_v36": "no_secret_leak_report_v36.json",
        "test_no_direct_order_bypass_v36": "no_direct_order_bypass_report_v36.json",
        "test_no_browser_automation_v36": "no_browser_automation_report_v36.json",
        "test_no_fake_transport_score_claimed_live_v36": "no_fake_transport_score_claimed_live_report_v36.json",
        "test_no_real_probe_run_to_execution_bridge_v36": "no_real_probe_run_to_execution_bridge_v36_report.json",
        "test_no_sprint_queue_to_execution_bridge_v36": "no_sprint_queue_to_execution_bridge_v36_report.json",
        "test_v35_still_passes_or_partial_expected_v36": "dummy_mission_state_report_v22.json",
    }
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    return assert_v36_report_named(candidates[stem])
