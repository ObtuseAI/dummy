from __future__ import annotations

from predator_mesh.v14.launch_readiness import LiquidityLaunchReadinessMatrix
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_liquidity_launch_blocker_report_includes_credentials_and_live_submit() -> None:
    report = LiquidityLaunchReadinessMatrix(forensics_report=fake_invalid_forensics_report()).blocker_report()

    assert "CREDENTIALS_INVALID" in report["blockers"]
    assert "LIVE_SUBMIT_DISABLED" in report["blockers"]
    assert report["verdict"] == "PARTIAL"
