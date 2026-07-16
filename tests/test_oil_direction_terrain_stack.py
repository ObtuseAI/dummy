from __future__ import annotations


def test_oil_terrain_marks_cl_and_brent_blockers_before_forecast() -> None:
    from predator_mesh.v20.terrain import OilDirectionTerrainStack

    stack = OilDirectionTerrainStack()
    report = stack.to_report()
    blocker = stack.source_blocker_report()

    assert report["verdict"] == "PARTIAL"
    assert "CL futures orderbook/trades" in report["required_source_needs"]
    assert blocker["exchange_native_missing"] is True
    assert blocker["blocked_sources"]
