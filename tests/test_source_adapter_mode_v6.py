from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict


def test_source_adapter_mode_v6_reports_terrain_truth() -> None:
    from predator_mesh.v16.source_adapter_truth import SourceAdapterTruthAlignment

    report = SourceAdapterTruthAlignment(pass_truth_verdict()).source_adapter_mode_report_v6()

    assert report["modes"]["kalshi_real_orderbook_liquidity"] == "REAL_READ_ONLY_BOUNDED"
    assert report["terrain_truth_verdict"] == "PASS_REAL_TERRAIN"
