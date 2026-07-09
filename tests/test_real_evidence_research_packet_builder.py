from __future__ import annotations


def test_real_evidence_research_packet_builder_prefers_real_but_labels_fixture() -> None:
    from predator_mesh.v19.research_ops import RealEvidenceResearchPacketBuilder

    report = RealEvidenceResearchPacketBuilder().to_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["packet_count"] == 5
    assert report["fixture_evidence_claimed_real"] is False
