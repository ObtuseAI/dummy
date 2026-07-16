from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_universe_coverage_scoreboard_has_all_terrain_rows() -> None:
    report = assert_v20_report("source_universe_coverage_scoreboard_v1.json", "coverage")
    terrains = {row["terrain"] for row in report["coverage"]}
    assert {"nasdaq", "oil", "crypto", "weather", "sports"} <= terrains
