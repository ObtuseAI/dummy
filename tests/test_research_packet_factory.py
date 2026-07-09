from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_research_packet_factory_generates_fixture_packets_for_all_domains() -> None:
    from predator_mesh.v18.research_packets import ResearchPacketFactory

    report = ResearchPacketFactory().to_report()

    assert_pass_report(report)
    assert set(report["domains"]) == DOMAINS
    assert report["packet_count"] == 5
    assert report["fake_evidence_created"] is False
