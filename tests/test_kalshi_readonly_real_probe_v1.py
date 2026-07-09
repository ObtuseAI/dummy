from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_kalshi_readonly_real_probe_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["blocker"] == "READONLY_ACCESS_UNAVAILABLE"
    assert report["execution_bridge_present"] is False
