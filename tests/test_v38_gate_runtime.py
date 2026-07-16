from __future__ import annotations

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v38.reports import V38ReportFactory
from tests.v38_test_helpers import assert_current_test_report


def test_v38_default_env_blocks_with_exact_operator_packet() -> None:
    report = assert_current_test_report(__file__)
    assert report["milestone_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["next_action"] == "OPERATOR_SET_EXACT_PUBLIC_PROBE_GATE"
    assert report["real_probe_run_allowed"] is False
    assert report["real_probe_run_count"] == 0
    assert report["real_evidence_count"] == 0
    assert report["real_scored_count"] == 0
    assert report["operator_packet"] == {
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    }
    assert report["missing_ack_probe_run"] is False
    assert report["fuzzy_ack_probe_run"] is False


def test_v38_fuzzy_ack_never_runs_probe_or_fails_final() -> None:
    reports = V38ReportFactory(
        env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "yes please trade"},
        enable_real_probe=True,
    ).build()
    gate = reports["v38_exact_operator_gate_recheck_v1_report.json"]
    mission = reports["dummy_mission_state_report_v24.json"]
    assert gate["ack_decision"] == "FAIL_FUZZY_ACK"
    assert gate["milestone_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert gate["real_probe_run_allowed"] is False
    assert gate["fuzzy_ack_probe_run"] is False
    assert mission["verdict"] == "PARTIAL"


def test_v38_exact_injected_env_selects_real_probe_run() -> None:
    reports = V38ReportFactory(env=EXACT_GATE_ENV, enable_real_probe=True).build()
    gate = reports["v38_exact_operator_gate_recheck_v1_report.json"]
    assert gate["ack_decision"] == "EXACT_ACK_VALID"
    assert gate["real_probe_run_allowed"] is True
    assert gate["selected_probe_mode"] == "REAL_PROBE_RUN"
