from __future__ import annotations


def test_v16_real_terrain_still_passes_or_degrades_cleanly_v18() -> None:
    from archive.report_scripts.generate_v18_reports import generate_prior_statuses_v18

    assert generate_prior_statuses_v18()["v16_real_terrain_status"] in {
        "PASS_REAL_TERRAIN",
        "PASS_REAL_TERRAIN_WITH_WARNINGS",
        "PARTIAL_NO_ELIGIBLE_MARKET",
        "PARTIAL_ENDPOINT_UNAVAILABLE",
        "UNKNOWN",
    }
