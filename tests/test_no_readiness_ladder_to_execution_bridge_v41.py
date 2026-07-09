from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_no_readiness_ladder_to_execution_bridge_v41() -> None:
    report = assert_current_test_report(__file__)
    assert report["readiness_ladder_to_execution_bridge_present"] is False
