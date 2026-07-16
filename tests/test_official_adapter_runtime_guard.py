from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_official_adapter_runtime_guard_blocks_repeated_unit_live_calls() -> None:
    report = assert_v20_report("official_adapter_runtime_guard_report_v1.json", "timeout_seconds")
    assert report["repeated_live_calls_in_unit_tests"] is False
