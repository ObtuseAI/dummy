from __future__ import annotations

from predator_mesh.v14.runtime_acceleration import TestRuntimeBudgetReport


def test_test_runtime_budget_report_preserves_timeout_guards() -> None:
    report = TestRuntimeBudgetReport(timeout_seconds_per_test=60).to_report()

    assert report["timeout_seconds_per_test"] == 60
    assert report["unbounded_network_allowed"] is False
    assert report["unbounded_subprocess_allowed"] is False
    assert report["verdict"] == "PASS"
