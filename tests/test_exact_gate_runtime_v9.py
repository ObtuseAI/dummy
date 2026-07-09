from __future__ import annotations

from predator_mesh.v41.reports import V41ReportFactory
from tests.v41_test_helpers import assert_current_test_report


def test_exact_gate_runtime_v9_blocks_missing_and_fuzzy_ack() -> None:
    report = assert_current_test_report(__file__)
    assert report["exact_gate_runtime_v9_status"] == "PASS_BLOCKED"
    assert report["gate_run_authorized"] is False
    assert report["missing_ack_probe_run"] is False
    fuzzy = V41ReportFactory(env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "read only please"}).build()
    fuzzy_report = fuzzy["exact_gate_runtime_v9_report.json"]
    assert fuzzy_report["ack_decision"] == "FAIL_FUZZY_ACK"
    assert fuzzy_report["gate_run_authorized"] is False
    assert fuzzy_report["fuzzy_ack_probe_run"] is False
