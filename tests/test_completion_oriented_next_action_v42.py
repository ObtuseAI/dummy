from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report, v42_enabled_reports


def test_completion_oriented_next_action_v42_never_selects_execution() -> None:
    report = assert_current_test_report(__file__)
    assert report["selected_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["selects_live_trading"] is False
    enabled = v42_enabled_reports()["completion_oriented_next_action_v42_report.json"]
    assert enabled["selected_next_action"] == "REAL_CALIBRATION_DEEPENING"
    assert enabled["selects_order_cancel"] is False
