from __future__ import annotations

from predator_mesh.v10.source_adapters import SourceAdapterPromotionEngine


def test_source_adapter_mode_report_counts_modes() -> None:
    report = SourceAdapterPromotionEngine().mode_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["mode_counts"]["LIVE_PUBLIC_BOUNDED"] >= 1
    assert report["mode_counts"]["SAMPLE_STATIC"] >= 1
    assert report["mode_counts"]["MOCK_ONLY_EXPLICIT"] >= 1
    assert report["partial_reason"] == "sample_or_mock_adapters_remaining"
