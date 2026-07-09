from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_domain_baseline_comparison_avoids_fake_market_implied_edges() -> None:
    from predator_mesh.v18.domain_baselines import DomainBaselineForecastEngineV2

    report = DomainBaselineForecastEngineV2().comparison_report()

    assert_pass_report(report)
    assert report["fake_edge_claimed"] is False
    assert all(item["market_implied_available"] is False for item in report["comparisons"])
