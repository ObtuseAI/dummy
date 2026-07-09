from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_edge_terrain_readiness_scoreboard_marks_no_trade_pressure() -> None:
    report = assert_v20_report("edge_terrain_readiness_scoreboard_v1.json", "readiness")
    assert all(row["forecast_readiness"] == "NO_TRADE" for row in report["readiness"])

