from __future__ import annotations

from tests.v34_test_helpers import v34_reports

SAFETY_REPORTS = [
    "no_secret_leak_report_v34.json",
    "no_kalshi_private_key_leak_report_v34.json",
    "no_source_api_key_leak_report_v34.json",
    "no_github_token_leak_report_v34.json",
    "no_llm_secret_leak_report_v34.json",
    "no_direct_order_bypass_report_v34.json",
    "no_direct_cancel_bypass_report_v34.json",
    "no_live_submit_still_disabled_report_v34.json",
    "no_caps_config_modification_report_v34.json",
    "readonly_only_source_activation_report_v34.json",
    "no_unauthorized_source_report_v34.json",
    "no_questionable_odds_scraping_report_v34.json",
    "no_unapproved_source_activation_report_v34.json",
    "no_commercial_source_without_approval_report_v34.json",
    "no_premium_feed_required_global_blocker_report_v34.json",
    "no_browser_automation_report_v34.json",
    "no_pageagent_report_v34.json",
    "no_dom_extraction_report_v34.json",
    "no_browser_research_lane_report_v34.json",
    "no_mined_repo_clone_report_v34.json",
    "no_mined_repo_import_report_v34.json",
    "no_mined_repo_execution_report_v34.json",
    "no_blind_mined_code_copy_report_v34.json",
    "no_fixture_claimed_real_report_v34.json",
    "no_replay_claimed_live_report_v34.json",
    "no_replay_score_claimed_live_report_v34.json",
    "no_proxy_claimed_exchange_native_report_v34.json",
    "no_cached_sample_claimed_live_report_v34.json",
    "no_stale_cached_evidence_scored_live_report_v34.json",
    "no_public_sample_evidence_scored_live_report_v34.json",
    "no_context_claimed_edge_report_v34.json",
    "no_example_market_canonical_center_report_v34.json",
    "no_unresolved_forecast_scored_report_v34.json",
    "no_ambiguous_settlement_scored_report_v34.json",
    "no_source_unavailable_forecast_scored_report_v34.json",
    "no_not_due_forecast_scored_report_v34.json",
    "no_adapter_fixture_scored_live_report_v34.json",
    "no_adapter_dry_run_scored_live_report_v34.json",
    "no_public_probe_failure_scored_live_report_v34.json",
    "no_disabled_probe_scored_live_report_v34.json",
    "no_outcome_fabrication_report_v34.json",
    "no_operator_enabled_probe_run_to_execution_bridge_report_v34.json",
    "no_minimal_live_public_probe_to_execution_bridge_report_v34.json",
    "no_live_public_evidence_ingestion_to_execution_bridge_report_v34.json",
    "no_settlement_evidence_join_to_execution_bridge_report_v34.json",
    "no_due_observation_run_to_execution_bridge_report_v34.json",
    "no_live_score_observation_to_execution_bridge_report_v34.json",
    "no_live_calibration_observation_to_execution_bridge_report_v34.json",
    "no_public_probe_cache_to_execution_bridge_report_v34.json",
    "no_enabled_probe_audit_to_execution_bridge_report_v34.json",
    "no_source_truth_to_execution_bridge_report_v34.json",
    "no_probe_sprint_to_execution_bridge_report_v34.json",
    "blunder_separation_recheck_v34.json",
    "dummy_canonical_identity_report_v34.json",
]


def test_v34_safety_invariants_present_and_passing() -> None:
    reports = v34_reports()
    missing = [name for name in SAFETY_REPORTS if name not in reports]
    assert missing == [], f"missing safety reports: {missing}"
    for name in SAFETY_REPORTS:
        report = reports[name]
        assert report["status"] == "PASS", f"{name}: {report.get('status')}"
        assert report["live_submit_disabled"] is True
        assert report["caps_unchanged"] is True
        assert report["execution_bridge_present"] is False
        assert report["secret_values_exposed"] is False
        assert report["source_api_keys_exposed"] is False
        assert report["github_tokens_exposed"] is False
        assert report["kalshi_private_keys_exposed"] is False
        assert report["llm_secrets_exposed"] is False
        assert report["order_endpoints_used"] is False
        assert report["cancel_endpoints_used"] is False
        assert report["private_endpoints_used"] is False


def test_v34_safety_invariants_no_browser_dom_or_mined_repo_additions() -> None:
    reports = v34_reports()
    for name in SAFETY_REPORTS:
        report = reports[name]
        assert report["browser_automation_added"] is False
        assert report["pageagent_added"] is False
        assert report["dom_extraction_added"] is False
        assert report["browser_research_lane_added"] is False
        assert report["mined_repo_cloned"] is False
        assert report["mined_repo_imported"] is False
        assert report["mined_repo_executed"] is False


def test_v34_safety_invariants_no_invalid_scoring_paths() -> None:
    reports = v34_reports()
    for name in SAFETY_REPORTS:
        report = reports[name]
        assert report["fixture_evidence_claimed_real"] is False
        assert report["replay_evidence_claimed_live"] is False
        assert report["replay_score_claimed_live"] is False
        assert report["proxy_evidence_claimed_exchange_native"] is False
        assert report["cached_sample_claimed_live"] is False
        assert report["stale_cached_evidence_scored_live"] is False
        assert report["public_sample_evidence_scored_live"] is False
        assert report["context_only_claimed_edge"] is False
        assert report["example_market_canonical_center"] is False
        assert report["unresolved_forecast_scored"] is False
        assert report["ambiguous_settlement_scored"] is False
        assert report["source_unavailable_forecast_scored"] is False
        assert report["not_due_forecast_scored"] is False
        assert report["adapter_fixture_scored_live"] is False
        assert report["adapter_dry_run_scored_live"] is False
        assert report["public_probe_failure_scored_live"] is False
        assert report["disabled_probe_scored_live"] is False
        assert report["missing_ack_probe_run"] is False
        assert report["fuzzy_ack_probe_run"] is False
        assert report["outcome_fabricated"] is False
