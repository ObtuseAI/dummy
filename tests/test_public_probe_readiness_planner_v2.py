from tests.v29_test_helpers import assert_v29_report_named


def test_public_probe_readiness_planner_v2_selects_only_safe_readonly_keyless_plans() -> None:
    report = assert_v29_report_named(
        "public_probe_readiness_planner_v2_report.json",
        "public_probe_readiness_status",
        "public_probe_ready_count",
        "public_probe_readiness_candidates",
    )

    assert report["public_probe_readiness_status"] == "PASS"
    assert report["public_probe_ready_count"] >= 3
    assert report["integration_mode_status"] == "DISABLED_BY_DEFAULT"
    assert report["browser_automation_added"] is False
    assert report["scraping_added"] is False
    assert report["source_api_keys_required_for_ready"] is False
    assert report["private_endpoints_used"] is False

    for candidate in report["public_probe_readiness_candidates"]:
        if candidate["readiness_verdict"] == "READY_DISABLED_BY_DEFAULT":
            assert candidate["method"] == "GET"
            assert candidate["requires_secret"] is False
            assert candidate["timeout_seconds"] <= 6
            assert candidate["integration_enabled_by_default"] is False
            assert candidate["live_execution_enabled"] is False
