from __future__ import annotations

from predator_mesh.v34.run import V34RuntimeBudgetReportV1, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_v34_runtime_budget_report_default_status() -> None:
    budget = V34RuntimeBudgetReportV1().build(build_default_v34_state(enable_network=False))

    assert budget.v34_runtime_budget_status == "PASS"
    assert budget.execution_bridge_present is False
    assert budget.probe_reconciliation_runtime_budget["max_requests_enabled"] == 4


def test_v34_runtime_budget_report_contract() -> None:
    report = assert_v34_report_named("v34_runtime_budget_report_v1.json", "v34_runtime_budget_status")

    assert report["v34_runtime_budget_status"] == "PASS"
    assert report["dashboard_cache_policy"] == "artifact-backed deterministic report slices"
