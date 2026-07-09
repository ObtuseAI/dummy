from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report, v40_enabled_reports


def test_completion_oriented_next_action_v40_default_gate_action() -> None:
    report = assert_current_test_report(__file__)
    assert report["selected_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["selects_live_trading"] is False
    assert report["selects_live_submit_caps"] is False
    assert report["selects_order_cancel"] is False


def test_completion_oriented_next_action_v40_enabled_sample_growth_action() -> None:
    report = v40_enabled_reports()["completion_oriented_next_action_v40_report.json"]
    assert report["selected_next_action"] in {"REAL_LIVE_SCORE_SAMPLE_EXPANSION", "REAL_CALIBRATION_DEEPENING"}
    assert report["selects_browser_or_mined_code"] is False
