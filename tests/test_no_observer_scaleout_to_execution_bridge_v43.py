from __future__ import annotations

from tests.v43_test_helpers import assert_current_test_report


def test_no_observer_scaleout_to_execution_bridge_v43_report() -> None:
    assert_current_test_report(__file__)
