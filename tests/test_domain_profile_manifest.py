from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_domain_profile_manifest_requires_sources_settlement_and_calibration() -> None:
    from predator_mesh.v18.domain_intelligence import DomainIntelligenceSpine

    report = DomainIntelligenceSpine().profile_manifest()

    assert_pass_report(report)
    assert set(report["profiles"]) == DOMAINS
    for profile in report["profile_manifest"].values():
        assert profile["required_settlement_facts"]
        assert profile["required_source_categories"]
        assert profile["calibration_profile_requirements"]
