from __future__ import annotations


def test_liquidity_attribution_keeps_warning_visible() -> None:
    from predator_mesh.v17.attribution import OutcomeAttributionEngine

    report = OutcomeAttributionEngine().liquidity_attribution_report(v16_warning="PASS_REAL_TERRAIN_WITH_WARNINGS")

    assert report["liquidity_warning_useful"] is True
    assert report["v16_warning"] == "PASS_REAL_TERRAIN_WITH_WARNINGS"
