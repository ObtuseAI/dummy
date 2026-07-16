from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_oil_direction_source_stack_contains_cme_ice_and_eia_candidates() -> None:
    report = assert_v20_report("oil_direction_source_stack_report_v1.json", "sources")
    ids = {source["source_id"] for source in report["sources"]}
    assert {"CME_CL_ENERGY_FUTURES", "ICE_BRENT_ENERGY_FUTURES", "EIA_OPEN_DATA"} <= ids
