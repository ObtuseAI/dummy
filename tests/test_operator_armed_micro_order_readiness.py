from __future__ import annotations

from predator_mesh.v14.launch_readiness import LiquidityLaunchReadinessMatrix
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_operator_armed_micro_order_readiness_stays_blocked_until_credential_repair() -> None:
    report = LiquidityLaunchReadinessMatrix(forensics_report=fake_invalid_forensics_report()).operator_readiness_report()

    assert report["ready_for_operator_armed_micro_order"] is False
    assert report["gate_output"] == "READY_FOR_OPERATOR_ARMED_MICRO_ORDER_ONLY_AFTER_CREDENTIAL_REPAIR"
    assert report["verdict"] == "PARTIAL"
