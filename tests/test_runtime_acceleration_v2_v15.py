from __future__ import annotations

from predator_mesh.v15.runtime_acceleration_v2 import (
    SAFE_PROOF_CACHE,
    RuntimeAccelerationMegaReportV2,
    SlowTestRemediationReportV2,
    TestRuntimeBudgetReportV2,
)


def test_full_regression_still_required() -> None:
    report = RuntimeAccelerationMegaReportV2().to_report()
    assert report["keeps_full_regression_required"] is True
    assert report["recursive_pytest_allowed"] is False
    assert any("pytest" in cmd for cmd in report["required_full_regression_commands"])


def test_timeout_budget_within_60s() -> None:
    report = TestRuntimeBudgetReportV2().to_report()
    assert report["timeout_seconds_per_test"] <= 60
    assert report["verdict"] == "PASS"


def test_safe_proof_cache_reuses_builder_result() -> None:
    SAFE_PROOF_CACHE.clear()
    calls = {"n": 0}

    def build():
        calls["n"] += 1
        return {"safe": True}

    first = SAFE_PROOF_CACHE.get_or_set("k", build)
    second = SAFE_PROOF_CACHE.get_or_set("k", build)
    assert first == second == {"safe": True}
    assert calls["n"] == 1


def test_slow_test_remediation_never_removes_tests() -> None:
    report = SlowTestRemediationReportV2().to_report()
    assert report["full_regression_required"] is True
    assert "network" in " ".join(report["remediation_actions"]).lower()
