from __future__ import annotations

from predator_mesh.v11.shadow_orders import ShadowOrderPacket


def test_shadow_order_packet_is_limit_only_and_blocked_by_default() -> None:
    packet = ShadowOrderPacket.sample()

    assert packet.intent.order_type == "limit"
    assert packet.intent.side in {"yes", "no"}
    assert packet.market_ticker
    assert packet.contract_ticker
    assert packet.sizing.size <= packet.sizing.max_size
    assert packet.price_limit.price_cents <= packet.price_limit.max_price_cents
    assert packet.no_model_output_authority is True
    assert packet.no_direct_submit_authority is True
    assert packet.blocked_reason == "LIVE_SUBMIT_DISABLED"
    assert packet.digest.digest
