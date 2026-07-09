from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_fail_escalation_guard_v2() -> None:
    report = assert_current_test_report(__file__)
    assert report["fail_escalation_guard_v2_status"] == "PASS"
    assert report["component_fail_escalates"] is True
    assert report["frontend_build_failure_escalates"] is True
    assert report["route_smoke_failure_escalates"] is True
    assert report["default_disabled_gate_is_partial"] is True
