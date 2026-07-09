from __future__ import annotations


def test_source_bloodline_promotion_v2_blocks_fixture_promotion_as_real() -> None:
    from predator_mesh.v19.bloodlines import SourceBloodlinePromotionV2

    report = SourceBloodlinePromotionV2().to_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["fixture_only_promoted_as_real"] is False
