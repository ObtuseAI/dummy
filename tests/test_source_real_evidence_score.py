from __future__ import annotations


def test_source_real_evidence_score_keeps_low_sample_explicit() -> None:
    from predator_mesh.v19.bloodlines import SourceBloodlinePromotionV2

    report = SourceBloodlinePromotionV2().real_evidence_score_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert all("sample_count" in item for item in report["scores"])
