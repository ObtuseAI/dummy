from __future__ import annotations


def test_source_fixture_penalty_prevents_real_promotion() -> None:
    from predator_mesh.v19.bloodlines import SourceBloodlinePromotionV2

    report = SourceBloodlinePromotionV2().fixture_penalty_report()
    assert report["verdict"] == "PASS"
    assert report["fixture_penalty_applied"] is True
