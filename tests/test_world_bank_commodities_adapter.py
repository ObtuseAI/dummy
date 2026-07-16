from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_world_bank_commodities_adapter_is_context_fallback_safe() -> None:
    report = assert_v20_report("world_bank_commodities_adapter_report_v1.json", "domain")
    assert report["domain"] == "commodities"
