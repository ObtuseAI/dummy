from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from archive.report_scripts.generate_v156_reports import generate_all_v156_reports_for_tests
from archive.report_scripts.generate_v157_reports import generate_all_v157_reports_for_tests
from archive.report_scripts.generate_v158_reports import generate_all_v158_reports_for_tests
from archive.report_scripts.generate_v159_reports import generate_all_v159_reports_for_tests
from archive.report_scripts.generate_v160_reports import generate_all_v160_reports_for_tests
from archive.report_scripts.generate_v161_reports import generate_all_v161_reports_for_tests
from archive.report_scripts.generate_v162_reports import generate_all_v162_reports_for_tests
from archive.report_scripts.generate_v163_reports import generate_all_v163_reports_for_tests
from archive.report_scripts.generate_v164_reports import generate_all_v164_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def pilot_approval(phrase: str = sgc.CONTROLLED_PILOT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "run one controlled production pilot via firewall", "scope": sgc.CONTROLLED_PILOT_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "per_order_fail_closed_acknowledgment": "per-order fail-closed checks", "pilot_auto_lock_acknowledgment": "immediate pilot auto-lock",
    }


def broker_readonly_approval(phrase: str = sgc.BROKER_READONLY_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "broker read-only verification only", "scope": sgc.BROKER_READONLY_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def repeat_approval(phrase: str = sgc.REPEAT_PILOT_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review a repeat controlled production pilot only", "scope": sgc.REPEAT_PILOT_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


class FakeFirewall:
    """NON-broker firewall double. Never contacts a real broker; asserts no market orders."""

    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False, "pilot_id": order.get("pilot_id")}


class FakeReadOnlyAdapter:
    """NON-broker read-only double. Never contacts a real broker; never submits or cancels."""

    def read_only_verify(self):
        return {"real_broker_contacted": False, "submit_call_made": False, "cancel_call_made": False, "account_status": "REDACTED"}


# --- V156 approval-file linter ---
def test_v156_default_absent_and_fixture_valid_no_write() -> None:
    d = generate_all_v156_reports_for_tests()["v156_approval_linter_controller_report.json"]
    assert d["approval_linter_controller_status"] == "PARTIAL_APPROVAL_FILES_ABSENT_OR_INCOMPLETE"
    assert d["approval_files_written"] == 0 and d["broker_contacted"] is False
    ok = generate_all_v156_reports_for_tests(pilot_approval=pilot_approval(), broker_readonly_approval=broker_readonly_approval(), repeat_approval=repeat_approval())["v156_approval_linter_controller_report.json"]
    assert ok["approval_linter_controller_status"] == "PASS_APPROVAL_FILES_LINTED_VALID"
    assert ok["approval_files_written"] == 0
    fuzzy = generate_all_v156_reports_for_tests(pilot_approval=pilot_approval("bad"))["v156_approval_linter_controller_report.json"]
    assert fuzzy["approval_linter_controller_status"] == "FAIL_CLOSED_INVALID_APPROVAL_FILE"
    assert_staged_safe(ok)


# --- V157 live-submit/caps audit ---
def test_v157_default_absent_and_fixture_confirmed_no_mutation() -> None:
    d = generate_all_v157_reports_for_tests()["v157_config_audit_controller_report.json"]
    assert d["config_audit_controller_status"] == "PARTIAL_LIVE_SUBMIT_OR_CAPS_CONFIRMATION_ABSENT"
    assert d["live_submit_changed"] is False and d["caps_changed"] is False
    ok = generate_all_v157_reports_for_tests(live_submit_operator_enabled=True, caps_config_present=True)["v157_config_audit_controller_report.json"]
    assert ok["config_audit_controller_status"] == "PASS_LIVE_SUBMIT_CAPS_CONFIRMED_READONLY"
    assert ok["live_submit_hash_before"] == ok["live_submit_hash_after"]
    assert ok["caps_hash_before"] == ok["caps_hash_after"]
    assert_staged_safe(d)


# --- V158 firewall adapter injection verification ---
def test_v158_default_absent_and_fixture_verified() -> None:
    d = generate_all_v158_reports_for_tests()["v158_firewall_adapter_controller_report.json"]
    assert d["firewall_adapter_controller_status"] == "PARTIAL_FIREWALL_ADAPTER_ABSENT"
    ok = generate_all_v158_reports_for_tests(firewall_adapter=FakeFirewall("x"))["v158_firewall_adapter_controller_report.json"]
    assert ok["firewall_adapter_controller_status"] == "PASS_FIREWALL_ADAPTER_INJECTION_VERIFIED"
    assert ok["real_broker_contacted"] is False
    assert_staged_safe(ok)


# --- V159 broker read-only verification ---
def test_v159_default_absent_and_fixture_verified_no_submit_cancel() -> None:
    d = generate_all_v159_reports_for_tests()["v159_broker_readonly_controller_report.json"]
    assert d["broker_readonly_controller_status"] == "PARTIAL_BROKER_READONLY_APPROVAL_OR_ADAPTER_ABSENT"
    assert d["real_broker_contacted"] is False
    ok = generate_all_v159_reports_for_tests(broker_readonly_approval=broker_readonly_approval(), readonly_adapter=FakeReadOnlyAdapter())["v159_broker_readonly_controller_report.json"]
    assert ok["broker_readonly_controller_status"] == "PASS_BROKER_READONLY_VERIFIED_NO_SUBMIT_CANCEL"
    assert ok["real_broker_contacted"] is False
    assert ok["submit_call_made"] is False and ok["cancel_call_made"] is False
    fuzzy = generate_all_v159_reports_for_tests(broker_readonly_approval=broker_readonly_approval("bad"), readonly_adapter=FakeReadOnlyAdapter())["v159_broker_readonly_controller_report.json"]
    assert fuzzy["broker_readonly_controller_status"] == "FAIL_CLOSED_INVALID_BROKER_READONLY_APPROVAL"
    assert_staged_safe(ok)


# --- V160 final readiness quorum ---
def test_v160_default_blocked_and_fixture_ready_no_submit() -> None:
    d = generate_all_v160_reports_for_tests()["v160_readiness_quorum_controller_report.json"]
    assert d["readiness_quorum_controller_status"] == "PARTIAL_FINAL_REAL_PILOT_QUORUM_BLOCKED"
    ok = generate_all_v160_reports_for_tests(approval_ready_override=True, config_ready_override=True, firewall_ready_override=True)["v160_readiness_quorum_controller_report.json"]
    assert ok["readiness_quorum_controller_status"] == "PASS_FINAL_REAL_PILOT_QUORUM_READY_NO_SUBMIT"
    assert ok["quorum_ready"] is True and ok["live_orders"] == 0
    assert_staged_safe(ok)


# --- V161 first real pilot fire gate ---
def test_v161_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v161_reports_for_tests()["v161_first_real_pilot_gate_controller_report.json"]
    assert d["first_real_pilot_gate_controller_status"] == "PARTIAL_FIRST_REAL_PILOT_NOT_ARMED"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v161_reports_for_tests(pilot_approval=pilot_approval(), quorum_ready_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v161-attempt-1"))["v161_first_real_pilot_gate_controller_report.json"]
    assert c["first_real_pilot_gate_controller_status"] == "PASS_FIRST_REAL_PILOT_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v161-attempt-1"
    assert c["pilot_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v161_dry_mode_missing_quorum_fuzzy_and_no_adapter_block() -> None:
    dry = generate_all_v161_reports_for_tests(pilot_approval=pilot_approval(), quorum_ready_override=True, mode_live_override=False, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v161_first_real_pilot_gate_controller_report.json"]
    assert dry["firewall_submit_invoked"] is False
    no_quorum = generate_all_v161_reports_for_tests(pilot_approval=pilot_approval(), quorum_ready_override=False, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v161_first_real_pilot_gate_controller_report.json"]
    assert no_quorum["firewall_submit_invoked"] is False
    fuzzy = generate_all_v161_reports_for_tests(pilot_approval=pilot_approval("bad"), quorum_ready_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v161_first_real_pilot_gate_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v161_reports_for_tests(pilot_approval=pilot_approval(), quorum_ready_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True)["v161_first_real_pilot_gate_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False and no_adapter["live_orders"] == 0


# --- V162 reconcile ---
def test_v162_default_partial_and_override_classified() -> None:
    d = generate_all_v162_reports_for_tests()["v162_reconcile_controller_report.json"]
    assert d["reconcile_controller_status"] == "PARTIAL_NO_FIRST_REAL_PILOT_TO_RECONCILE"
    assert d["order_state"] == "NO_ATTEMPT"
    r = generate_all_v162_reports_for_tests(v161_final_override={"first_real_pilot_gate_controller_status": "PASS_FIRST_REAL_PILOT_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1}, outcome_state="FILLED")["v162_reconcile_controller_report.json"]
    assert r["reconcile_controller_status"] == "PASS_FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
    assert r["order_state"] == "FILLED" and r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V163 forensic review ---
def test_v163_default_partial_and_override_reviewed() -> None:
    d = generate_all_v163_reports_for_tests()["v163_forensic_controller_report.json"]
    assert d["forensic_controller_status"] == "PARTIAL_NO_FIRST_REAL_PILOT_TO_REVIEW"
    r = generate_all_v163_reports_for_tests(v162_final_override={"reconcile_controller_status": "PASS_FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED", "order_state": "FILLED"})["v163_forensic_controller_report.json"]
    assert r["forensic_controller_status"] == "PASS_FIRST_REAL_PILOT_FORENSIC_REVIEWED"
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V164 repeat eligibility decision ---
def test_v164_default_stop_and_fixture_review_ready() -> None:
    d = generate_all_v164_reports_for_tests()["v164_repeat_eligibility_controller_report.json"]
    assert d["repeat_eligibility_controller_status"] == "PARTIAL_REPEAT_ELIGIBILITY_BLOCKED"
    assert d["eligibility_decision"] == "STOP_NO_REAL_PILOT_PROOF"
    assert d["repeat_pilot_submitted"] is False and d["live_orders"] == 0
    ok = generate_all_v164_reports_for_tests(repeat_approval=repeat_approval(), first_pilot_override=True)["v164_repeat_eligibility_controller_report.json"]
    assert ok["repeat_eligibility_controller_status"] == "PASS_REPEAT_ELIGIBILITY_REVIEW_READY_LOCKED"
    assert ok["eligibility_decision"] == "REPEAT_REVIEW_READY_LOCKED"
    fuzzy = generate_all_v164_reports_for_tests(repeat_approval=repeat_approval("bad"), first_pilot_override=True)["v164_repeat_eligibility_controller_report.json"]
    assert fuzzy["repeat_eligibility_controller_status"] == "FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"
    assert_staged_safe(ok)


# --- safety / locks default across the whole bundle ---
def test_v156_to_v164_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v156_reports_for_tests,
        generate_all_v157_reports_for_tests,
        generate_all_v158_reports_for_tests,
        generate_all_v159_reports_for_tests,
        generate_all_v160_reports_for_tests,
        generate_all_v161_reports_for_tests,
        generate_all_v162_reports_for_tests,
        generate_all_v163_reports_for_tests,
        generate_all_v164_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
