from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_v36_runtime_budget() -> None:
    report = assert_current_test_report(__file__)
    budget = report["real_probe_runtime_budget"]
    assert budget["real_network_only_if_gate_enabled"] is True
    assert budget["unit_tests_use_fixtures"] is True
    assert report["execution_bridge_present"] is False
