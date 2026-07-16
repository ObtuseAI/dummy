from __future__ import annotations

from predator_mesh.v39.reports import V39ReportFactory
from tests.v39_test_helpers import assert_current_test_report


def test_exact_gate_runtime_execution_v7() -> None:
    report = assert_current_test_report(__file__)
    assert report["exact_gate_runtime_execution_v7_status"] == "PASS_BLOCKED"
    assert report["ack_decision"] == "FAIL_MISSING_ACK"
    assert report["safe_gate_metadata"]["mode_present"] is False
    assert report["safe_gate_metadata"]["ack_present"] is False
    assert report["safe_gate_metadata"]["exact_ack_valid"] is False
    assert report["safe_gate_metadata"]["read_only_scope"] is False
    assert report["environment_dumped"] is False


def test_fuzzy_v39_ack_is_partial_and_never_runs() -> None:
    reports = V39ReportFactory(env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "trade now"}, enable_real_probe=True).build()
    report = reports["exact_gate_runtime_execution_v7_report.json"]
    assert report["ack_decision"] == "FAIL_FUZZY_ACK"
    assert report["real_probe_run_allowed"] is False
    assert report["fuzzy_ack_probe_run"] is False
    assert reports["dummy_mission_state_report_v25.json"]["verdict"] == "PARTIAL"
