from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_weather_source_stack_contains_official_public_sources() -> None:
    report = assert_v20_report("weather_source_stack_report_v1.json", "sources")
    ids = {source["source_id"] for source in report["sources"]}
    assert {"NWS_API_WEATHER_GOV", "NOAA_NHC", "ECMWF_OPEN_DATA"} <= ids
