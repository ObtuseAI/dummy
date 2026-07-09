from __future__ import annotations


def test_forecast_activation_decision_uses_no_trade_for_unsafe_states() -> None:
    from predator_mesh.v19.forecast_activation import ForecastActivationEngine

    report = ForecastActivationEngine().decision_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert all(item["decision"] for item in report["decisions"])
