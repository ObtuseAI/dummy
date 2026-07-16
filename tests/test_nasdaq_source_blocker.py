from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_nasdaq_source_blocker_names_exchange_native_blocker() -> None:
    report = assert_v20_report("nasdaq_source_blocker_report_v1.json", "blocked_sources")
    assert report["exchange_native_missing"] is True
    assert "NQ futures orderbook/trades" in report["blocked_sources"]
