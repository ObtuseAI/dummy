from __future__ import annotations

from predator_mesh.v12.source_adapter_closure import SourceAdapterClosurePass


def test_source_adapter_closure_promotes_kalshi_liquidity_source_only_when_bounded() -> None:
    report = SourceAdapterClosurePass().to_report()

    assert report["verdict"] == "PASS"
    assert report["promoted_sources"][0]["source_name"] == "kalshi_real_orderbook_liquidity"
    assert report["promoted_sources"][0]["mode"] == "LIVE_PUBLIC_BOUNDED"
    assert report["promoted_sources"][0]["source_legality"] == "PASS"
    assert report["promoted_sources"][0]["timeout_guard"] == "PASS"
