from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_no_sample_expansion_controller_to_execution_bridge_v40() -> None:
    report = assert_current_test_report(__file__)
    assert report["sample_expansion_controller_to_execution_bridge_present"] is False
    assert report["execution_bridge_present"] is False
