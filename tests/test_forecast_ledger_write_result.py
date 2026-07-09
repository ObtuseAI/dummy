from __future__ import annotations


def test_forecast_ledger_write_result_is_immutable_and_counted() -> None:
    from predator_mesh.v19.forecast_activation import ForecastActivationEngine

    report = ForecastActivationEngine().ledger_write_result_report()
    assert report["verdict"] == "PASS"
    assert report["outcome_leakage_detected"] is False
    assert report["ledger_write_count"] >= 0
