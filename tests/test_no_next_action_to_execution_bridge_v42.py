from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_no_next_action_to_execution_bridge_v42() -> None:
    assert_current_test_report(__file__)["next_action_to_execution_bridge_present"] is False
