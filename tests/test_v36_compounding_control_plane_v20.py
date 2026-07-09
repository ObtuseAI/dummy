from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_v36_compounding_control_plane_v20() -> None:
    report = assert_current_test_report(__file__)
    assert report["v35_fail_escalation_preserved"] is True
    assert report["execution_bridge_present"] is False
