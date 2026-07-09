from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_settlement_rule_mapper_builds_profiles_for_all_domains() -> None:
    from predator_mesh.v18.settlement import SettlementRuleMapper

    report = SettlementRuleMapper().to_report()

    assert_pass_report(report)
    assert set(report["domains"]) == DOMAINS
    assert report["fabricates_truth"] is False
