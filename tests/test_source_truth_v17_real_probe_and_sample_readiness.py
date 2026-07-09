from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_source_truth_v17_real_probe_and_sample_readiness() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_trading_readiness_claim"] is True
    assert report["execution_bridge_present"] is False
