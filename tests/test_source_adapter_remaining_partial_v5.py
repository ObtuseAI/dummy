from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict


def test_source_adapter_remaining_partial_v5_keeps_non_kalshi_static_domains_explicit() -> None:
    from predator_mesh.v16.source_adapter_truth import SourceAdapterTruthAlignment

    report = SourceAdapterTruthAlignment(pass_truth_verdict()).remaining_partial_report_v5()

    assert "weather" in report["remaining_partial_modes"]
    assert report["kalshi_real_orderbook_liquidity"] == "REAL_READ_ONLY_BOUNDED"
