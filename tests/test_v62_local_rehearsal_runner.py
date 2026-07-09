from __future__ import annotations

import json

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v62.reports import FORBIDDEN_SIM_FIELDS, LOCAL_REHEARSAL_SCOPE
from scripts.generate_v62_reports import generate_all_v62_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def local_rehearsal_approval(phrase: str = sgc.LOCAL_REHEARSAL_DESIGN_PHRASE) -> dict:
    return {
        "exact_phrase": phrase,
        "operator": "operator:chris",
        "timestamp": "2026-07-05T21:00:00Z",
        "reason": "design-validated local-only rehearsal simulation",
        "scope": LOCAL_REHEARSAL_SCOPE,
        "expiration": "2026-07-06T21:00:00Z",
        "no_broker_payloads_acknowledgment": "no broker payloads",
        "no_order_submission_acknowledgment": "no order submission",
        "no_live_trading_acknowledgment": "no live trading",
        "no_live_submit_acknowledgment": "no live-submit enablement",
        "no_caps_modification_acknowledgment": "no caps modification",
    }


def test_v62_default_partial_without_local_rehearsal_approval() -> None:
    reports = generate_all_v62_reports_for_tests()
    gate = reports["v62_local_only_rehearsal_gate_report.json"]
    assert_staged_safe(gate)
    assert gate["v61_baseline_status"] == "PASS_V61_BASELINE_READBACK"
    assert gate["local_only_rehearsal_gate_status"] == "PARTIAL_LOCAL_REHEARSAL_APPROVAL_ABSENT"
    assert gate["simulation_entry_count"] == 0
    final = reports["final_report_v62.json"]
    assert final["verdict"] == "PARTIAL"
    assert "LOCAL_REHEARSAL_APPROVAL_ABSENT" in final["current_blockers"]


def test_v62_exact_approval_runs_inert_local_only_simulation(tmp_path) -> None:
    sim_dir = tmp_path / "sim"
    reports = generate_all_v62_reports_for_tests(approval_input=local_rehearsal_approval(), write_sim=True, sim_dir=sim_dir)
    gate = reports["v62_local_only_rehearsal_gate_report.json"]
    ledger = reports["v62_local_only_simulation_ledger_report.json"]
    assert gate["local_only_rehearsal_gate_status"] == "PASS_LOCAL_ONLY_REHEARSAL_SIMULATED"
    assert gate["simulation_entry_count"] == 4
    assert gate["simulation_is_inert"] is True
    assert ledger["inert"] is True
    assert reports["final_report_v62.json"]["verdict"] == "PASS"

    files = sorted(sim_dir.glob("*.json"))
    assert len(files) == 4
    for path in files:
        entry = json.loads(path.read_text(encoding="utf-8"))
        assert entry["simulated"] is True
        assert entry["executed"] is False
        assert entry["broker_payload_present"] is False
        assert entry["order_intent_present"] is False
        assert not any(field in entry for field in FORBIDDEN_SIM_FIELDS)


def test_v62_fuzzy_approval_fails_closed() -> None:
    reports = generate_all_v62_reports_for_tests(approval_input=local_rehearsal_approval("I approve Dummy to run rehearsals"))
    gate = reports["v62_local_only_rehearsal_gate_report.json"]
    assert gate["local_only_rehearsal_gate_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert gate["simulation_entry_count"] == 0


def test_v62_safety_and_locks() -> None:
    reports = generate_all_v62_reports_for_tests()
    for name, report in reports.items():
        if name == "final_report_v62.json":
            continue
        assert_staged_safe(report)
