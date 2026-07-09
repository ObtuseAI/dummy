from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_v18_domain_baselines_integrate_with_v17_forecast_snapshots() -> None:
    from predator_mesh.v18.integration import V18ForecastSnapshotIntegration

    report = V18ForecastSnapshotIntegration().to_report()

    assert_pass_report(report)
    assert report["forecast_snapshot_records"] == 5
    assert report["outcome_leakage_detected"] is False
