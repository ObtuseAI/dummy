from __future__ import annotations

from predator_mesh.v13.source_adapter_closure import SourceAdapterClosurePassV2
from tests.v13_test_helpers import real_snapshot_result


def test_source_adapter_closure_v2_promotes_real_kalshi_when_real_terrain_proven() -> None:
    report = SourceAdapterClosurePassV2(real_snapshot_result()).to_report()

    assert report["verdict"] == "PASS"
    assert report["promoted_sources"][0]["source_name"] == "kalshi_real_orderbook_liquidity"
    assert report["promoted_sources"][0]["mode"] == "REAL_READ_ONLY_BOUNDED"
