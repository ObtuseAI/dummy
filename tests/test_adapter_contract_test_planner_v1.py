from tests.v29_test_helpers import assert_v29_report_named


def test_adapter_contract_test_planner_v1_plans_fixture_backed_contracts_with_integration_disabled() -> None:
    report = assert_v29_report_named(
        "adapter_contract_test_planner_v1_report.json",
        "adapter_contract_test_planner_status",
        "contract_test_case_kinds",
        "contract_ready_count",
    )

    assert report["adapter_contract_test_planner_status"] == "PASS"
    assert report["contract_ready_count"] >= 5
    assert {
        "success_normalization",
        "source_unavailable",
        "stale_evidence",
        "malformed_response",
        "terms_blocked",
        "rate_limit_timeout",
        "fixture_not_live",
        "cached_stale_not_scored",
        "no_execution_bridge",
    } <= set(report["contract_test_case_kinds"])
    assert report["unit_tests_fixture_backed"] is True
    assert report["integration_tests_disabled_by_default"] is True
    assert report["requires_explicit_readonly_mode"] is True
    assert report["recursive_pytest"] is False
    assert report["live_trading_paths_tested_or_enabled"] is False
