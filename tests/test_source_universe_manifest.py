from __future__ import annotations

from tests.v20_test_helpers import assert_source_candidate


def test_source_universe_manifest_includes_required_categories_without_real_fixture_claims() -> None:
    from predator_mesh.v20.source_universe import SourceUniverse

    manifest = SourceUniverse().manifest_report()
    sources = manifest["sources"]

    assert manifest["verdict"] == "PASS"
    assert manifest["source_count"] >= 80
    assert {"CME_NQ_ES_FUTURES", "EIA_OPEN_DATA", "CCXT_PUBLIC_PLAN", "NWS_API_WEATHER_GOV", "SPORTSRADAR_LICENSED"} <= {source["source_id"] for source in sources}
    assert all(source["truth_source_role"] != "GITHUB_TRUTH_SOURCE" for source in sources)
    assert all(source["fixture_claimed_real"] is False for source in sources)
    assert_source_candidate(sources[0])
