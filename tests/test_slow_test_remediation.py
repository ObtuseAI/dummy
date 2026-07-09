from __future__ import annotations

from predator_mesh.v14.runtime_acceleration import SlowTestRemediationReport


def test_slow_test_remediation_report_recommends_sharding_without_recursive_pytest() -> None:
    report = SlowTestRemediationReport().to_report()

    assert report["recursive_pytest_allowed"] is False
    assert report["remediation_actions"]
    assert all("pytest" not in action.lower() or "recursive" not in action.lower() for action in report["remediation_actions"])
    assert report["verdict"] == "PASS"
