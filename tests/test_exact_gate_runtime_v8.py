from __future__ import annotations

from predator_mesh.v40.reports import V40ReportFactory
from tests.v40_test_helpers import assert_current_test_report


def test_exact_gate_runtime_v8_default_blocks_without_env_dump() -> None:
    report = assert_current_test_report(__file__)
    assert report["exact_gate_runtime_v8_status"] == "PASS_BLOCKED"
    assert report["ack_decision"] == "FAIL_MISSING_ACK"
    assert report["safe_gate_metadata"]["mode_present"] is False
    assert report["safe_gate_metadata"]["ack_present"] is False
    assert report["safe_gate_metadata"]["exact_ack_valid"] is False
    assert report["environment_dumped"] is False


def test_exact_gate_runtime_v8_fuzzy_ack_never_runs_probes() -> None:
    reports = V40ReportFactory(env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ ONLY maybe trade"}, enable_real_probe=True).build()
    report = reports["exact_gate_runtime_v8_report.json"]
    assert report["ack_decision"] == "FAIL_FUZZY_ACK"
    assert report["v40_new_real_probe_count"] == 0
    assert report["fuzzy_ack_probe_run"] is False
    assert reports["dummy_mission_state_report_v26.json"]["verdict"] == "PARTIAL"
