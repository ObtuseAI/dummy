from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_domain_baseline_forecast_engine_v2_ledgers_one_pre_outcome_snapshot_per_domain() -> None:
    from predator_mesh.v18.domain_baselines import DomainBaselineForecastEngineV2

    report = DomainBaselineForecastEngineV2().to_report()

    assert_pass_report(report)
    assert set(report["domains"]) == DOMAINS
    assert report["ledger_snapshot_count"] == 5
    assert report["heavy_ml_used"] is False
    assert report["outcome_leakage_detected"] is False
