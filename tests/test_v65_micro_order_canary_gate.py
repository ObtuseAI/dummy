from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v65.reports import LIVE_CANARY_SCOPE
from archive.report_scripts.generate_v65_reports import generate_all_v65_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def live_canary_packet(phrase: str = sgc.LIVE_CANARY_PHRASE) -> dict:
    return {
        "exact_phrase": phrase,
        "operator": "operator:chris",
        "timestamp": "2026-07-05T21:00:00Z",
        "reason": "arm single tiny live limit canary via firewall",
        "scope": LIVE_CANARY_SCOPE,
        "expiration": "2026-07-06T21:00:00Z",
        "kill_switch_acknowledgment": "kill-switch armed and required",
        "rollback_acknowledgment": "immediate fail-closed rollback required",
        "no_market_order_acknowledgment": "no market order permitted",
        "caps_unchanged_acknowledgment": "caps unchanged unless separately approved",
        "firewall_only_acknowledgment": "livebrokerfirewall only",
    }


def test_v65_default_partial_without_live_canary_approval() -> None:
    reports = generate_all_v65_reports_for_tests()
    gate = reports["v65_micro_order_canary_gate_controller_report.json"]
    assert_staged_safe(gate)
    assert gate["v64_baseline_status"] == "PASS_V64_BASELINE_READBACK"
    assert gate["micro_order_canary_gate_status"] == "PARTIAL_LIVE_CANARY_APPROVAL_ABSENT"
    assert gate["arming_state"] == "NOT_ARMED"
    assert gate["order_fired"] is False
    final = reports["final_report_v65.json"]
    assert final["verdict"] == "PARTIAL"
    assert "LIVE_CANARY_APPROVAL_ABSENT" in final["current_blockers"]


def test_v65_exact_approval_arms_conceptually_but_never_fires() -> None:
    reports = generate_all_v65_reports_for_tests(approval_input=live_canary_packet())
    gate = reports["v65_micro_order_canary_gate_controller_report.json"]
    arming = reports["v65_arming_state_report.json"]
    assert gate["micro_order_canary_gate_status"] == "PASS_MICRO_ORDER_CANARY_GATE_READY_LOCKED"
    assert gate["arming_state"] == "ARMED_CONCEPTUAL_NO_FIRE"
    assert gate["approval_validated"] is True
    assert gate["order_fired"] is False
    assert gate["submit_call_made"] is False
    assert gate["broker_payload_sent"] is False
    assert gate["live_submit_changed"] is False
    assert gate["caps_changed"] is False
    assert arming["conceptual_only"] is True
    assert gate["prerequisite_gates_ok"] is True
    assert reports["final_report_v65.json"]["verdict"] == "PASS"
    assert reports["final_report_v65.json"]["current_next_action"] == "MICRO_ORDER_CANARY_GATE_READY_LOCKED_ARMED_CONCEPTUAL_NO_FIRE"
    assert_staged_safe(gate)


def test_v65_fuzzy_live_canary_packet_not_armed() -> None:
    gate = generate_all_v65_reports_for_tests(approval_input=live_canary_packet("I approve arming a live canary"))["v65_micro_order_canary_gate_controller_report.json"]
    assert gate["arming_state"] == "NOT_ARMED"
    assert gate["micro_order_canary_gate_status"] == "PARTIAL_LIVE_CANARY_APPROVAL_ABSENT"
    assert gate["order_fired"] is False


def test_v65_proofs_and_safety() -> None:
    reports = generate_all_v65_reports_for_tests(approval_input=live_canary_packet())
    gate = reports["v65_micro_order_canary_gate_controller_report.json"]
    for key in [
        "pre_submit_denial_proof_status",
        "limit_order_only_proof_status",
        "no_market_order_proof_status",
        "livebrokerfirewall_only_proof_status",
        "kill_switch_proof_status",
        "rollback_proof_status",
        "idempotency_proof_status",
        "exposure_caps_readonly_proof_status",
        "live_submit_disabled_proof_status",
    ]:
        assert gate[key].startswith("PASS")
    for name, report in reports.items():
        if name == "final_report_v65.json":
            continue
        assert_staged_safe(report)
