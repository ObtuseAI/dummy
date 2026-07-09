from __future__ import annotations


def test_evidence_contradiction_resolver_summarizes_contradictions() -> None:
    from predator_mesh.v19.research_ops import EvidenceContradictionResolver

    report = EvidenceContradictionResolver().to_report()
    assert report["verdict"] == "PASS"
    assert report["contradictions_visible"] is True
