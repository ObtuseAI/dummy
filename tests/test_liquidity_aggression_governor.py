from __future__ import annotations

from predator_mesh.v11.aggression import LiquidityAggressionGovernor


def test_liquidity_aggression_governor_escalates_good_liquidity() -> None:
    decision = LiquidityAggressionGovernor().evaluate(LiquidityAggressionGovernor.sample_inputs())

    assert decision.decision in {
        "ESCALATE_TO_SHADOW_ORDER",
        "APPROVE_FIREWALL_REHEARSAL",
        "REQUIRE_MORE_EVIDENCE",
        "REDUCE_SIZE",
        "STARVE_LIQUIDITY_SIGNAL",
        "NO_TRADE",
        "QUARANTINE_MARKET",
    }
    assert decision.decision == "ESCALATE_TO_SHADOW_ORDER"
    assert decision.score.total > 0
