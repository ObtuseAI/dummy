from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_edge_feature_contribution_report_reflects_no_trade_weights() -> None:
    report = assert_v20_report("edge_feature_contribution_report_v1.json", "contributions")
    assert all("contribution" in contribution for contribution in report["contributions"])
