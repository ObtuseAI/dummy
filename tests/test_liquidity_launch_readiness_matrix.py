from __future__ import annotations

from predator_mesh.v14.launch_readiness import LiquidityLaunchReadinessMatrix
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_liquidity_launch_readiness_matrix_scores_blocked_credentials() -> None:
    report = LiquidityLaunchReadinessMatrix(forensics_report=fake_invalid_forensics_report()).to_report()

    assert 0 <= report["readiness_score"] <= 1
    assert report["gate_output"] == "READY_FOR_OPERATOR_ARMED_MICRO_ORDER_ONLY_AFTER_CREDENTIAL_REPAIR"
    assert "credential readiness" in report["categories"]
