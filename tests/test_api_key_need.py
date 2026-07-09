from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_api_key_need_lists_env_names_without_values() -> None:
    report = assert_v20_report("api_key_need_report_v1.json", "needs")
    assert report["api_key_values_exposed"] is False
    assert all(need["value_exposed"] is False for need in report["needs"])

