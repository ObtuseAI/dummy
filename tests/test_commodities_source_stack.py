from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_commodities_source_stack_contains_energy_and_ag_public_context() -> None:
    report = assert_v20_report("commodities_source_stack_report_v1.json", "sources")
    ids = {source["source_id"] for source in report["sources"]}
    assert {"EIA_OPEN_DATA", "USDA_NASS_QUICK_STATS", "WORLD_BANK_COMMODITY_PRICES"} <= ids

