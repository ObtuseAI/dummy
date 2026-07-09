from __future__ import annotations


def test_forecast_snapshot_ledger_records_immutable_pre_outcome_snapshot() -> None:
    from predator_mesh.v17.forecasts import ForecastSnapshotLedger
    from tests.v17_test_helpers import fixture_forecasts_and_outcomes

    forecasts, _ = fixture_forecasts_and_outcomes()
    ledger = ForecastSnapshotLedger()
    result = ledger.record(forecasts[0])

    assert result.recorded is True
    assert ledger.snapshots[0].probability == 0.7
    assert ledger.snapshots[0].future_outcome_known is False
