from __future__ import annotations


def test_v16_real_terrain_outcome_integration_preserves_v16_truth_as_evidence() -> None:
    from predator_mesh.v17.v16_integration import V16RealTerrainOutcomeIntegration

    report = V16RealTerrainOutcomeIntegration().to_report()

    assert report["v16_terrain_truth_preserved"] is True
    assert report["live_order_data_used"] is False
