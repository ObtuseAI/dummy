from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_v34_default_path_reverification_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["gate_state"] == "DISABLED_BY_DEFAULT"
    assert report["ack_status"] == "FAIL_MISSING_ACK"
    assert report["probe_run_count"] == 0
    assert report["live_public_evidence"] == 0
    assert report["observed"] == 0
    assert report["live_scored"] == 0
    assert report["due"] == 4
    assert report["unresolved"] == 4
    assert report["sports_mode"] == "FIXTURE_REPLAY_ONLY"
    assert report["verdict"] == "PARTIAL"
    assert report["execution_bridge_present"] is False
