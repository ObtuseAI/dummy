from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_domain_scoreboard_v4_summarizes_source_and_terrain_readiness() -> None:
    report = assert_v20_report("domain_scoreboard_v4_report.json", "rows")
    assert report["real_readonly_active_total"] == 0
    assert report["fixture_total"] > 0
