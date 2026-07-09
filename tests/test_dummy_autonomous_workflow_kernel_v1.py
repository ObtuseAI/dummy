from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_dummy_autonomous_workflow_kernel_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["workflow_kernel_status"] == "PASS"
    assert "EXACT_GATED_REAL_PROBE" in report["registered_lanes"]
    assert report["selected_lane"] == "EXACT_GATED_REAL_PROBE"
    assert report["real_probe_gate_status"] == "PROBE_DISABLED_BY_DEFAULT"
    assert report["current_next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
