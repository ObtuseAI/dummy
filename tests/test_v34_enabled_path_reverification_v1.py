from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_v34_enabled_path_reverification_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["gate_state"] == "ENABLED_READONLY_PUBLIC_PROBES"
    assert report["probe_run_count"] == 3
    assert report["evidence"] == 3
    assert report["observed"] == 3
    assert report["scored"] == 3
    assert report["unresolved"] == 1
    assert report["transport_mode"] == "FAKE"
    assert report["verdict"] == "PARTIAL"
    assert report["execution_bridge_present"] is False
