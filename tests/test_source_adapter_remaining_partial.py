from __future__ import annotations

from predator_mesh.v12.source_adapter_closure import SourceAdapterClosurePass


def test_source_adapter_remaining_partial_report_keeps_weather_sports_macro_as_safe_samples() -> None:
    report = SourceAdapterClosurePass().remaining_partial_report()

    assert report["verdict"] == "PARTIAL"
    assert "macro_calendar_static_metadata" in report["remaining_sample_sources"]
    assert "weather_public_sample" in report["remaining_sample_sources"]
    assert "sports_schedule_static" in report["remaining_sample_sources"]
    assert "prediction_market_cross_price_explicit_mock" in report["remaining_mock_sources"]
