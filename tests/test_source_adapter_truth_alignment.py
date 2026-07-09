from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict


def test_source_adapter_truth_alignment_promotes_kalshi_only_on_real_pass() -> None:
    from predator_mesh.v16.source_adapter_truth import SourceAdapterTruthAlignment

    report = SourceAdapterTruthAlignment(pass_truth_verdict()).to_report()

    assert report["kalshi_orderbook_liquidity_mode"] == "REAL_READ_ONLY_BOUNDED"
    assert report["unauthorized_sources"] == []
