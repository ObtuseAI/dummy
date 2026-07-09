from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_census_macro_adapter_is_fallback_safe() -> None:
    report = assert_v20_report("census_macro_adapter_report_v1.json", "deterministic_fallback")
    assert report["deterministic_fallback"] is True

