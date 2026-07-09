from __future__ import annotations


def test_evidence_quality_score_marks_low_evidence_and_staleness() -> None:
    from predator_mesh.v19.research_ops import EvidenceQualityScore

    report = EvidenceQualityScore().to_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["quality_scores"]
    assert report["low_evidence_explicit"] is True
