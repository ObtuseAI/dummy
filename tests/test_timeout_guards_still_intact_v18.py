from __future__ import annotations


def test_timeout_guards_still_intact_v18() -> None:
    from predator_mesh.v18.research_packets import ResearchPacketFactory
    from predator_mesh.v18.settlement import SettlementRuleMapper

    assert ResearchPacketFactory.max_lane_timeout_s <= 10
    assert SettlementRuleMapper.max_request_timeout_s <= 10
