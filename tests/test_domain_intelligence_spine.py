from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_domain_intelligence_spine_covers_v18_domains_with_no_trade_pressure() -> None:
    from predator_mesh.v18.domain_intelligence import DomainIntelligenceSpine

    report = DomainIntelligenceSpine().to_report()

    assert_pass_report(report)
    assert set(report["domains"]) == DOMAINS
    assert report["domain_count"] == 5
    assert all(profile["domain_specific_no_trade_triggers"] for profile in report["profiles"])
