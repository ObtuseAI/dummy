from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_research_packet_no_trade_pressure_is_visible_for_weak_sources() -> None:
    from predator_mesh.v18.research_packets import ResearchPacketFactory

    report = ResearchPacketFactory().no_trade_pressure_report()

    assert_pass_report(report)
    assert report["no_trade_pressure_visible"] is True
    assert report["pressure_count"] >= 5
