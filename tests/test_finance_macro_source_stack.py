from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_finance_macro_source_stack_contains_official_macro_context() -> None:
    report = assert_v20_report("finance_macro_source_stack_report_v1.json", "sources")
    ids = {source["source_id"] for source in report["sources"]}
    assert {"FRED_ALFRED_MACRO_CONTEXT", "BLS_API", "SEC_EDGAR", "TREASURY_YIELD_DATA"} <= ids

