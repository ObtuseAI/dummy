from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_research_packet_manifest_links_packet_ids_to_domains_and_proofs() -> None:
    from predator_mesh.v18.research_packets import ResearchPacketFactory

    report = ResearchPacketFactory().manifest()

    assert_pass_report(report)
    assert set(report["packet_domains"].values()) == DOMAINS
    assert all(report["proof_refs_by_packet"].values())
