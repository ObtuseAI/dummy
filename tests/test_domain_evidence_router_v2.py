from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_domain_evidence_router_v2_routes_all_terrain_to_research_and_forecast() -> None:
    report = assert_v20_report("domain_evidence_router_v2_report.json", "routes", "blockers")
    assert report["feeds_research_packets"] is True
    assert report["feeds_forecast_pipeline"] is True
