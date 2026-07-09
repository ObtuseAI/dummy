from __future__ import annotations

from predator_mesh.v14.source_adapter_promotion import SourceAdapterPromotionMegaPass
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_source_adapter_mode_v4_counts_remaining_modes() -> None:
    report = SourceAdapterPromotionMegaPass(forensics_report=fake_invalid_forensics_report()).mode_report_v4()

    assert report["mode_counts"]["SAMPLE_STATIC_FALLBACK"] >= 1
    assert report["mode_counts"]["MOCK_ONLY_EXPLICIT"] >= 1
    assert report["verdict"] == "PARTIAL"
