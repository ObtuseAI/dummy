from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_v35_runtime_budget_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["v35_runtime_budget_status"] == "PASS"
    assert report["qc_runtime_budget"]["unit_tests_use_fixtures"] is True
    assert report["qc_runtime_budget"]["live_network_only_if_gate_enabled"] is True
    assert report["dashboard_cache_policy"] == "artifact-backed deterministic report slices"
    assert report["execution_bridge_present"] is False
