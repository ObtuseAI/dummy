from __future__ import annotations

from predator_mesh.v14.repair_wizard import KalshiReadOnlyRetestPlan


def test_kalshi_readonly_retest_plan_has_safe_commands_and_expected_outcomes() -> None:
    report = KalshiReadOnlyRetestPlan().to_report()

    assert "python scripts/generate_v14_reports.py" in report["safe_retest_commands"]
    assert "PASS" in report["expected_outcomes"]
    assert "PARTIAL" in report["expected_outcomes"]
    assert report["verdict"] == "PASS"
