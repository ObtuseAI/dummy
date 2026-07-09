from __future__ import annotations

from tests.v20_test_helpers import assert_source_candidate, assert_v20_report


def test_massive_source_candidate_manifest_contains_required_source_ids() -> None:
    report = assert_v20_report("massive_source_candidate_manifest_v1.json", "sources", "source_ids")
    assert {"CME_NQ_ES_FUTURES", "EIA_OPEN_DATA", "NWS_API_WEATHER_GOV", "CCXT_PUBLIC_PLAN"} <= set(report["source_ids"])
    assert len(report["sources"]) >= 80
    assert_source_candidate(report["sources"][0])

