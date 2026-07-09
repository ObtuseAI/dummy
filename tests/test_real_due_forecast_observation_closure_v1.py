from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_real_due_forecast_observation_closure_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_fabrication"] is True
    assert report["execution_bridge_present"] is False
