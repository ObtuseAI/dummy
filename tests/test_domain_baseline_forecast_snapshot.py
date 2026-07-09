from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_domain_baseline_forecast_snapshot_report_marks_fixture_vs_real() -> None:
    from predator_mesh.v18.domain_baselines import DomainBaselineForecastEngineV2

    report = DomainBaselineForecastEngineV2().snapshot_report()

    assert_pass_report(report)
    assert set(report["snapshot_domains"]) == DOMAINS
    assert report["fixture_snapshot_count"] == 5
    assert report["real_evidence_snapshot_count"] == 0
