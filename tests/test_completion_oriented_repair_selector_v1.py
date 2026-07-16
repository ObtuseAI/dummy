from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_completion_oriented_repair_selector_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["completion_repair_selector_status"] == "PASS"
    assert report["selected_repair_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["selects_live_trading"] is False


def test_completion_repair_selector_enabled_path_expands_sample() -> None:
    report = v39_enabled_reports()["completion_oriented_repair_selector_v1_report.json"]
    assert report["selected_repair_action"] == "REAL_LIVE_SCORE_SAMPLE_EXPANSION"
    assert report["selects_order_cancel"] is False
