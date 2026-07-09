from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_v40_baseline_readback_v1_preserves_counts_and_safety() -> None:
    report = assert_current_test_report(__file__)
    assert report["v40_baseline_readback_v1_status"] == "PASS_V40_BASELINE_READBACK"
    assert report["v39_baseline_real_scored_count"] >= 3
    assert report["v40_new_real_scored_count"] >= 3
    assert report["v40_cumulative_real_scored_count"] >= 6
    assert report["v40_source_truth_v21_status"] == "PASS"
    assert report["v40_no_trade_discipline_status"] == "PASS_NO_TRADE_DISCIPLINE_RECORDED"
