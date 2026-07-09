from __future__ import annotations


def test_forecast_activation_engine_writes_fixture_or_real_snapshots_without_leakage() -> None:
    from predator_mesh.v19.forecast_activation import ForecastActivationEngine

    report = ForecastActivationEngine().to_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["outcome_leakage_detected"] is False
    assert report["heavy_ml_used"] is False
