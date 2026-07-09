from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_real_live_calibration_seed_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["execution_bridge_present"] is False
