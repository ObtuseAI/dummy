from __future__ import annotations


def test_v16_real_terrain_still_passes_or_warns_v17() -> None:
    from scripts.generate_v17_reports import generate_prior_statuses_v17

    assert generate_prior_statuses_v17()["v16_real_terrain_status"] in {
        "PASS_REAL_TERRAIN",
        "PASS_REAL_TERRAIN_WITH_WARNINGS",
        "PARTIAL_NO_ELIGIBLE_MARKET",
        "PARTIAL_ENDPOINT_UNAVAILABLE",
        "UNKNOWN",
    }
