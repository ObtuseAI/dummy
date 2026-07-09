from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_domain_baseline_confidence_policy_is_conservative_for_fixture_evidence() -> None:
    from predator_mesh.v18.domain_baselines import DomainBaselineForecastEngineV2

    report = DomainBaselineForecastEngineV2().confidence_policy_report()

    assert_pass_report(report)
    assert report["conservative_confidence"] is True
    assert report["max_fixture_confidence"] <= 0.55
