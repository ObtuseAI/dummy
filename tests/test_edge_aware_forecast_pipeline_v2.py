from __future__ import annotations


def test_edge_aware_forecast_pipeline_uses_source_sufficiency_no_trade_gate() -> None:
    from predator_mesh.v20.forecast_pipeline import EdgeAwareForecastPipelineV2

    report = EdgeAwareForecastPipelineV2().to_report()

    assert report["verdict"] == "PARTIAL"
    assert report["no_heavy_ml"] is True
    assert report["outcome_leakage_detected"] is False
    assert report["no_trade_decision_count"] >= 2

