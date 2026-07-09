from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_autonomous_next_action_selector_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["next_action_selector_status"] == "PASS"
    assert report["decision"]["action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["decision"]["lane"] == "EXACT_GATED_REAL_PROBE"
    assert report["safety_checks"]["exact_gate_required"] is True
    assert report["safety_checks"]["real_probe_run_allowed"] is False
