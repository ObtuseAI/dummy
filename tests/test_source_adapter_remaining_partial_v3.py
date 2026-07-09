from __future__ import annotations

from predator_mesh.v14.source_adapter_promotion import SourceAdapterPromotionMegaPass


def test_source_adapter_remaining_partial_v3_lists_weather_sports_macro_and_cross_price() -> None:
    report = SourceAdapterPromotionMegaPass().remaining_partial_report_v3()

    assert "weather_public_sample" in report["remaining_sample_sources"]
    assert "sports_schedule_static" in report["remaining_sample_sources"]
    assert "prediction_market_cross_price_explicit_mock" in report["remaining_mock_sources"]
    assert report["verdict"] == "PARTIAL"
