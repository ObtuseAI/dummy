from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_weather_edge_terrain_stack_uses_official_public_sources() -> None:
    report = assert_v20_report("weather_edge_terrain_stack_report_v1.json", "public_context_sources")
    assert "NWS forecast" in report["required_source_needs"]
