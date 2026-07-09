from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_settlement_no_trade_pressure_lists_domain_specific_blockers() -> None:
    from predator_mesh.v18.settlement import SettlementRuleMapper

    report = SettlementRuleMapper().no_trade_pressure_report()

    assert_pass_report(report)
    assert report["pressure_count"] == 5
    assert all(item["reasons"] for item in report["pressures"])
