from __future__ import annotations

from predator_mesh.v13.source_adapter_closure import SourceAdapterClosurePassV2


def test_source_adapter_remaining_partial_v2_keeps_non_kalshi_sources_explicit() -> None:
    report = SourceAdapterClosurePassV2().remaining_partial_report_v2()

    assert "weather_public_sample" in report["remaining_sample_sources"]
    assert "prediction_market_cross_price_explicit_mock" in report["remaining_mock_sources"]
    assert report["verdict"] == "PARTIAL"
