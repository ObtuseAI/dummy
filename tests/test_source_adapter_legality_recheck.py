from __future__ import annotations

from predator_mesh.v14.source_adapter_promotion import SourceAdapterLegalityRecheck


def test_source_adapter_legality_recheck_blocks_unauthorized_sources() -> None:
    report = SourceAdapterLegalityRecheck().to_report()

    assert report["unauthorized_sources"] == []
    assert report["unbounded_scraping"] is False
    assert report["verdict"] == "PASS"
