from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict, real_snapshot


def test_stale_quote_risk_v6_includes_snapshot_proof_ref() -> None:
    from predator_mesh.v16.liquidity_reports import LiquidityModelTerrainReporter

    report = LiquidityModelTerrainReporter(real_snapshot(), pass_truth_verdict()).stale_quote_risk_report_v6()

    assert report["terrain_truth_verdict"] == "PASS_REAL_TERRAIN"
    assert report["source_snapshot_proof_ref"]
