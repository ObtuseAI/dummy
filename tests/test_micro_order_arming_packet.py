from __future__ import annotations

from predator_mesh.v11.micro_order import MicroOrderArmingPacket


def test_micro_order_arming_packet_requires_proofs_and_limit_order() -> None:
    packet = MicroOrderArmingPacket.sample()

    assert packet.limit_order_only is True
    assert packet.max_size <= packet.config_cap_size
    assert packet.market_orders_allowed is False
    assert packet.proof_refs.edge_candidate
    assert packet.proof_refs.no_direct_order_bypass
    assert packet.requires_operator_acknowledgement is True
