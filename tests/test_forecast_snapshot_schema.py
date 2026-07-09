from __future__ import annotations


def test_forecast_snapshot_schema_requires_probability_confidence_domain_and_refs() -> None:
    from predator_mesh.v17.forecasts import ForecastSnapshotLedger

    report = ForecastSnapshotLedger.schema_report()

    assert {"probability", "confidence", "market_id", "domain", "timestamp", "source_refs"}.issubset(report["required_fields"])
    assert report["immutable_after_recording"] is True
