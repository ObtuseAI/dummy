from __future__ import annotations

from predator_mesh.v11.liquidity import LiveLiquidityProofEngine, LiquidityProofVerdict


def test_liquidity_proof_engine_approves_good_rehearsal_packet() -> None:
    packet = LiveLiquidityProofEngine().evaluate(LiveLiquidityProofEngine.sample_opportunity())

    assert packet.verdict == LiquidityProofVerdict.LIQUIDITY_REHEARSAL_APPROVED
    assert packet.attack_readiness.ready_for_shadow_order is True
    assert packet.execution_terrain.limit_order_only is True
    assert packet.live_submit_required is False
    assert packet.proof_refs


def test_liquidity_proof_engine_blocks_bad_liquidity() -> None:
    opportunity = LiveLiquidityProofEngine.sample_opportunity(liquidity_score=0.10)
    packet = LiveLiquidityProofEngine().evaluate(opportunity)

    assert packet.verdict == LiquidityProofVerdict.NO_TRADE_LIQUIDITY_TOO_THIN
    assert "liquidity_too_thin" in packet.reasons
