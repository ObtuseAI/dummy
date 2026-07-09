from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_settlement_ambiguity_detector_generates_no_trade_pressure() -> None:
    from predator_mesh.v18.settlement import SettlementAmbiguityDetector, SettlementRuleMapper

    report = SettlementAmbiguityDetector(SettlementRuleMapper().profiles()).to_report()

    assert_pass_report(report)
    assert report["ambiguous_settlement_generates_no_trade"] is True
    assert report["ambiguous_profile_count"] >= 1
