from __future__ import annotations

from predator_mesh.v11.micro_order import MicroOrderArmingPacket, MicroOrderReadinessVerdict


def test_micro_order_readiness_is_blocked_when_live_submit_disabled() -> None:
    readiness = MicroOrderArmingPacket.sample().evaluate_readiness(live_submit_enabled=False)

    assert isinstance(readiness, MicroOrderReadinessVerdict)
    assert readiness.verdict == "BLOCKED_LIVE_SUBMIT_DISABLED"
    assert readiness.live_submit_enabled is False
    assert readiness.would_submit is False
