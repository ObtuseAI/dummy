from __future__ import annotations

from predator_mesh.v14.micro_order_dry_run import MicroOrderDryRunBlockerReport
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_micro_order_dry_run_blocker_lists_non_submit_reasons() -> None:
    report = MicroOrderDryRunBlockerReport(forensics_report=fake_invalid_forensics_report()).to_report()

    assert report["would_submit"] is False
    assert "CREDENTIALS_INVALID" in report["blockers"]
    assert "REAL_TERRAIN_NOT_PROVEN" in report["blockers"]
    assert "LIVE_SUBMIT_DISABLED" in report["blockers"]
    assert report["verdict"] == "PARTIAL"
