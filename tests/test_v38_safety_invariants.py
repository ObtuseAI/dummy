from __future__ import annotations

from tests.v38_test_helpers import v38_reports


def test_v38_safety_invariants_cover_live_trading_browser_mined_and_scoring_modes() -> None:
    reports = v38_reports()
    for name, report in reports.items():
        if name == "final_report_v38.json":
            continue
        assert report["live_submit_disabled"] is True, name
        assert report["caps_unchanged"] is True, name
        assert report["execution_bridge_present"] is False, name
        assert report["live_submit_enabled"] is False, name
        assert report["order_endpoints_used"] is False, name
        assert report["cancel_endpoints_used"] is False, name
        assert report["secret_values_exposed"] is False, name
        assert report["browser_automation_added"] is False, name
        assert report["pageagent_added"] is False, name
        assert report["dom_extraction_added"] is False, name
        assert report["mined_repo_cloned"] is False, name
        assert report["mined_repo_imported"] is False, name
        assert report["mined_repo_executed"] is False, name
        assert report["fake_transport_score_claimed_live"] is False, name
        assert report["fixture_evidence_scored_live"] is False, name
        assert report["stale_cache_scored_live"] is False, name
        assert report["missing_ack_probe_run"] is False, name
        assert report["fuzzy_ack_probe_run"] is False, name
        assert report["ambiguous_settlement_scored"] is False, name
        assert report["source_unavailable_forecast_scored"] is False, name
        assert report["not_due_forecast_scored"] is False, name
        assert report["unresolved_forecast_scored"] is False, name

