from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_nasdaq_direction_source_stack_prioritizes_exchange_native_blocked_sources() -> None:
    report = assert_v20_report("nasdaq_direction_source_stack_report_v1.json", "sources")
    assert report["source_count"] > 0
    assert any(source["source_id"] == "CME_NQ_ES_FUTURES" for source in report["sources"])
