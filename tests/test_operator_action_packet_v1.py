from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_operator_action_packet_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["operator_action_packet_status"] == "PASS"
    assert report["probe_gate_packet"]["DUMMY_PUBLIC_PROBE_MODE"] == "1"
    assert report["probe_gate_packet"]["DUMMY_PUBLIC_PROBE_ACK"] == "READ_ONLY_PUBLIC_PROBES_ONLY"
    assert report["requests_live_submit_enablement"] is False
    assert report["requests_caps_modification"] is False
