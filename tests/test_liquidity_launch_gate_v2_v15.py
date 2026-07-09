from __future__ import annotations

from predator_mesh.v15.launch_readiness_v2 import LiquidityLaunchReadinessMatrixV2, MicroOrderLaunchGateV2
from predator_mesh.v15.retry_gate_v2 import RealTerrainRetryGateV2
from predator_mesh.v15.credential_shape_repair import KalshiCredentialShapeRepairEngine
from predator_mesh.v15.credential_source_conflict_resolver import KalshiCredentialSourceConflictResolver
from tests.v15_test_helpers import MALFORMED_BACKSLASH_ENV, forensics_with_env, bridge_with_env


def test_malformed_shape_gate_output_requires_shape_repair() -> None:
    forensics = forensics_with_env(MALFORMED_BACKSLASH_ENV)
    repair = KalshiCredentialShapeRepairEngine(forensics=forensics)
    resolver = KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(MALFORMED_BACKSLASH_ENV))
    gate = RealTerrainRetryGateV2(repair_engine=repair, conflict_resolver=resolver)
    matrix = LiquidityLaunchReadinessMatrixV2(forensics_report=forensics.to_report(), retry_gate=gate)
    result = matrix.gate_output()
    assert result == MicroOrderLaunchGateV2.READY_ONLY_AFTER_CREDENTIAL_SHAPE_REPAIR


def test_gate_never_returns_ready_without_live_submit_disabled_check() -> None:
    forensics = forensics_with_env(MALFORMED_BACKSLASH_ENV)
    matrix = LiquidityLaunchReadinessMatrixV2(forensics_report=forensics.to_report())
    report = matrix.to_report()
    assert report["live_submit_disabled"] is True
    assert report["caps_unmodified"] is True
    assert report["not_a_live_order_trigger"] is True


def test_gate_output_is_rehearsal_only_signal() -> None:
    forensics = forensics_with_env(MALFORMED_BACKSLASH_ENV)
    matrix = LiquidityLaunchReadinessMatrixV2(forensics_report=forensics.to_report())
    report = matrix.to_report()
    assert report["rehearsal_only"] is True
    assert report["operator_armed_micro_order_ready"] is False


def test_gate_output_values_are_exact_enum_members() -> None:
    values = {member.value for member in MicroOrderLaunchGateV2}
    assert values == {
        "READY_FOR_OPERATOR_ARMED_MICRO_ORDER_REHEARSAL",
        "READY_ONLY_AFTER_CREDENTIAL_SHAPE_REPAIR",
        "READY_ONLY_AFTER_AUTH_REPAIR",
        "READY_ONLY_AFTER_REAL_TERRAIN_PROOF",
        "BLOCKED_LIVE_SUBMIT_DISABLED",
        "BLOCKED_CAPS_NOT_VERIFIED",
        "NOT_READY",
    }
