from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


_EXPLICIT_REPORTS = {
    "dashboard_v22": "dashboard_v22_report_v1.json",
    "normalized_evidence_packet_manifest": "normalized_evidence_packet_manifest_v1.json",
    "kalshi_market_discovery_recheck_v22": "kalshi_market_discovery_recheck_v22_report.json",
    "forecast_write_candidate_manifest": "forecast_write_candidate_manifest_v1.json",
    "forecast_snapshot_write_proof": "forecast_snapshot_write_proof_v1.json",
    "no_trade_write_proof": "no_trade_write_proof_v1.json",
    "outcome_observer_queue_v1": "outcome_observer_queue_v1_report.json",
    "forecast_snapshot_ledger_write_v22": "forecast_snapshot_ledger_write_v22_report.json",
    "no_trade_ledger_write_v22": "no_trade_ledger_write_v22_report.json",
    "observer_queue_ledger_write_v22": "observer_queue_ledger_write_v22_report.json",
    "ledger_write_integrity_check_v22": "ledger_write_integrity_check_v22_report.json",
    "edge_source_acquisition_engine_v2": "edge_source_acquisition_engine_v2_report.json",
    "github_adapter_implementation_queue_v2": "github_adapter_implementation_queue_v2_report.json",
    "compounding_control_plane_v5": "compounding_control_plane_v5_report.json",
    "domain_scoreboard_v6": "domain_scoreboard_v6_report.json",
    "forecast_write_breakthrough_scoreboard": "forecast_write_breakthrough_scoreboard_v1.json",
    "edge_terrain_activation_scoreboard": "edge_terrain_activation_scoreboard_v1.json",
    "dummy_mission_state_v22": "dummy_mission_state_report_v8.json",
    "v22_runtime_budget": "v22_runtime_budget_report_v1.json",
    "kalshi_mapping_call_limiter_v22": "kalshi_mapping_call_limiter_v22_report.json",
    "dashboard_cache_policy_v4": "dashboard_cache_policy_v4_report.json",
    "report_chain_runtime_profiler_v5": "report_chain_runtime_profiler_v5_report.json",
    "no_secret_leak_v22": "no_secret_leak_report_v22.json",
    "no_kalshi_private_key_leak_v22": "no_kalshi_private_key_leak_report_v22.json",
    "no_source_api_key_leak_v22": "no_source_api_key_leak_report_v22.json",
    "no_github_token_leak_v22": "no_github_token_leak_report_v22.json",
    "no_llm_secret_leak_v22": "no_llm_secret_leak_report_v22.json",
    "no_direct_order_bypass_v22": "no_direct_order_bypass_report_v22.json",
    "no_direct_cancel_bypass_v22": "no_direct_cancel_bypass_report_v22.json",
    "no_live_submit_still_disabled_v22": "no_live_submit_still_disabled_report_v22.json",
    "no_caps_config_modification_v22": "no_caps_config_modification_report_v22.json",
    "readonly_only_source_activation_v22": "readonly_only_source_activation_report_v22.json",
    "no_unauthorized_source_v22": "no_unauthorized_source_report_v22.json",
    "no_questionable_odds_scraping_v22": "no_questionable_odds_scraping_report_v22.json",
    "no_unapproved_source_activation_v22": "no_unapproved_source_activation_report_v22.json",
    "no_commercial_source_without_approval_v22": "no_commercial_source_without_approval_report_v22.json",
    "no_fixture_claimed_real_v22": "no_fixture_claimed_real_report_v22.json",
    "no_context_claimed_edge_v22": "no_context_claimed_edge_report_v22.json",
    "no_outcome_fabrication_v22": "no_outcome_fabrication_report_v22.json",
    "no_github_repo_code_execution_v22": "no_github_repo_code_execution_report_v22.json",
    "no_forecast_to_execution_bridge_v22": "no_forecast_to_execution_bridge_report_v22.json",
    "no_observer_to_execution_bridge_v22": "no_observer_to_execution_bridge_report_v22.json",
    "blunder_separation_v22": "blunder_separation_recheck_v22.json",
    "dummy_canonical_identity_v22": "dummy_canonical_identity_report_v22.json",
    "timeout_guards_still_intact_v22": "v22_runtime_budget_report_v1.json",
    "v17_truth_loop_still_passes_v22": "final_report_v22.json",
    "v18_domain_foundation_still_passes_or_partial_expected_v22": "final_report_v22.json",
    "v19_activation_architecture_still_passes_or_partial_expected_v22": "final_report_v22.json",
    "v20_source_universe_still_passes_or_partial_expected_v22": "final_report_v22.json",
    "v21_source_activation_still_passes_v22": "final_report_v22.json",
}


def report_name_for_test(test_file: str | Path) -> str:
    stem = Path(test_file).stem.removeprefix("test_")
    if stem in _EXPLICIT_REPORTS:
        return _EXPLICIT_REPORTS[stem]
    return f"{stem}_report_v1.json"


def assert_no_execution_or_secrets(report: dict) -> None:
    text = json.dumps(report, default=str)
    banned_fragments = [
        "BEGIN PRIVATE KEY",
        "END PRIVATE KEY",
        "github_pat_",
        "ghp_",
        "raw_prompt",
        "api_key_value",
        "source_api_key_value",
        "private_key_pem",
        "LiveBrokerFirewall.submit(",
    ]
    for fragment in banned_fragments:
        assert fragment not in text, fragment
    assert report.get("secret_values_exposed") is False
    assert report.get("live_submit_disabled") is True
    assert report.get("caps_unchanged") is True


def assert_pass_or_partial(report: dict) -> None:
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert_no_execution_or_secrets(report)


@lru_cache(maxsize=1)
def v22_reports() -> dict[str, dict]:
    from archive.report_scripts.generate_v22_reports import generate_all_v22_reports_for_tests

    return generate_all_v22_reports_for_tests(enable_network=False)


def assert_v22_report_named(report_name: str, *required_keys: str) -> dict:
    reports = v22_reports()
    assert report_name in reports, report_name
    report = reports[report_name]
    assert_pass_or_partial(report)
    for key in required_keys:
        assert key in report
    return report


def assert_current_test_report(test_file: str | Path) -> dict:
    return assert_v22_report_named(report_name_for_test(test_file), "workstream")
