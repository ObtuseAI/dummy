from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_nws_weather_adapter_is_readonly_and_timeout_guarded() -> None:
    report = assert_v20_report("nws_weather_adapter_report_v1.json", "adapter_id")
    assert report["read_only_only"] is True
    assert report["write_endpoints_called"] == []
