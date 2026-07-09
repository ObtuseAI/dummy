from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report, v40_enabled_reports


def test_expanded_settlement_join_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["validates_family_market_metric_source_timestamp"] is True
    assert report["scores_created_here"] is False
    assert report["expanded_settlement_join_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"


def test_expanded_settlement_join_v1_enabled() -> None:
    report = v40_enabled_reports()["expanded_settlement_join_v1_report.json"]
    assert report["expanded_settlement_join_status"] == "PASS_EXPANDED_SETTLEMENT_JOIN"
    assert report["v40_new_settlement_compatible_count"] > 0
