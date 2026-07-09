from __future__ import annotations

from predator_mesh.v14.source_adapter_promotion import SourceAdapterPromotionMegaPass
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_source_adapter_promotion_mega_keeps_kalshi_fallback_when_real_terrain_blocked() -> None:
    report = SourceAdapterPromotionMegaPass(forensics_report=fake_invalid_forensics_report()).to_report()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["kalshi_orderbook_liquidity_mode"] == "SAMPLE_STATIC_FALLBACK"
    assert report["unsafe_promotions"] == []
