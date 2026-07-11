from __future__ import annotations

from pathlib import Path

from predator_mesh import staged_gate_common as sgc
from archive.report_scripts.generate_v245_reports import generate_all_v245_reports_for_tests
from archive.report_scripts.generate_v246_reports import generate_all_v246_reports_for_tests
from archive.report_scripts.generate_v247_reports import generate_all_v247_reports_for_tests
from archive.report_scripts.generate_v248_reports import generate_all_v248_reports_for_tests
from archive.report_scripts.generate_v249_reports import generate_all_v249_reports_for_tests
from archive.report_scripts.generate_v250_reports import generate_all_v250_reports_for_tests
from archive.report_scripts.generate_v251_reports import generate_all_v251_reports_for_tests
from archive.report_scripts.generate_v252_reports import generate_all_v252_reports_for_tests
from archive.report_scripts.generate_v253_reports import generate_all_v253_reports_for_tests
from archive.report_scripts.generate_v254_reports import generate_all_v254_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
ROOT = Path(sgc.ROOT)


def pilot_approval(phrase: str = sgc.CONTROLLED_PILOT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-06T21:00:00Z",
        "reason": "run one controlled production pilot via firewall", "scope": sgc.CONTROLLED_PILOT_SCOPE,
        "expiration": "2026-07-07T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "per_order_fail_closed_acknowledgment": "per-order fail-closed checks", "pilot_auto_lock_acknowledgment": "immediate pilot auto-lock",
    }


class FakeFirewall:
    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False}


def _safe(report: dict) -> None:
    assert_staged_safe(report)
    assert report.get("runtime_approvals_created_by_dummy") is False
    assert report.get("approval_files_written", 0) == 0
    assert report.get("real_live_orders_submitted_count", 0) == 0
    assert report.get("real_broker_contacted") is False
    assert report.get("scale_applied") is False
    assert report.get("autonomous_trading_enabled") is False


# --- V245 appliance baseline (always PASS) ---
def test_v245_appliance_baseline_ready() -> None:
    d = generate_all_v245_reports_for_tests()["v245_operator_ready_appliance_baseline_controller_report.json"]
    assert d["operator_ready_appliance_baseline_controller_status"] == "PASS_OPERATOR_READY_APPLIANCE_BASELINE_READY"
    assert d["appliance_state_classification"]
    _safe(d)


# --- V246 appliance pack (read-only, no writes) ---
def test_v246_appliance_pack_ready_readonly() -> None:
    d = generate_all_v246_reports_for_tests()["v246_operator_ready_appliance_pack_controller_report.json"]
    assert d["operator_ready_appliance_pack_controller_status"] == "PASS_OPERATOR_READY_APPLIANCE_PACK_READY_READONLY"
    assert d["appliance_pack"]["not_approval"] is True
    assert d["not_approval_markers"]["appliance_pack"] == "NOT_APPROVAL"
    assert d["approval_files_written"] == 0
    _safe(d)


# --- V247 external authority rehearsal (inert, exact/fuzzy/broad cases) ---
def test_v247_rehearsal_inert_cases() -> None:
    d = generate_all_v247_reports_for_tests()["v247_external_authority_rehearsal_controller_report.json"]
    assert d["external_authority_rehearsal_controller_status"] == "PASS_EXTERNAL_AUTHORITY_REHEARSAL_COMPLETE_INERT"
    cases = {c["case"]: c for c in d["rehearsal_cases"]}
    assert cases["exact_valid_fixture"]["validator_accepted"] is True
    assert cases["fuzzy_approval"]["validator_accepted"] is False
    assert cases["broad_blanket_live_trading"]["validator_accepted"] is False
    assert cases["absent_manifest"]["validator_accepted"] is False
    assert cases["missing_operator_metadata"]["validator_accepted"] is False
    # hash-only: raw phrase never serialized
    assert sgc.CONTROLLED_PILOT_PHRASE not in str(d["rehearsal_cases"])
    _safe(d)


# --- V248 adapter contract kit (non-broker double) ---
def test_v248_default_awaits_and_non_broker_double_ready() -> None:
    d = generate_all_v248_reports_for_tests()["v248_adapter_contract_kit_controller_report.json"]
    assert d["adapter_contract_kit_controller_status"] == "PARTIAL_ADAPTER_CONTRACT_KIT_AWAITS_EXTERNAL_ADAPTER"
    assert d["contract_kit"]["market_order_rejection_requirement"] is True
    ok = generate_all_v248_reports_for_tests(firewall_adapter=FakeFirewall("kit"))["v248_adapter_contract_kit_controller_report.json"]
    assert ok["adapter_contract_kit_controller_status"] == "PASS_ADAPTER_CONTRACT_KIT_READY_NON_BROKER_DOUBLE"
    assert ok["real_broker_contacted"] is False and ok["live_orders"] == 0
    _safe(ok)


# --- V249 live-submit/caps rehearsal (immutable hashes) ---
def test_v249_default_blocked_and_fixture_ready_hashes_unchanged() -> None:
    d = generate_all_v249_reports_for_tests()["v249_live_submit_caps_rehearsal_controller_report.json"]
    assert d["live_submit_caps_rehearsal_controller_status"] == "PARTIAL_LIVE_SUBMIT_CAPS_REHEARSAL_BLOCKED_BY_ABSENT_EXTERNAL_CONFIG"
    assert d["live_submit_hash_unchanged"] is True and d["caps_hash_unchanged"] is True
    assert d["live_submit_changed"] is False and d["caps_changed"] is False
    ok = generate_all_v249_reports_for_tests(config_confirmed_override=True)["v249_live_submit_caps_rehearsal_controller_report.json"]
    assert ok["live_submit_caps_rehearsal_controller_status"] == "PASS_LIVE_SUBMIT_CAPS_REHEARSAL_READY_IMMUTABLE"
    assert ok["live_submit_hash_unchanged"] is True and ok["caps_hash_unchanged"] is True
    _safe(ok)


# --- V250 first-proof command center (read-only UI flags) ---
def test_v250_command_center_readonly() -> None:
    d = generate_all_v250_reports_for_tests()["v250_first_proof_command_center_controller_report.json"]
    assert d["first_proof_command_center_controller_status"] == "PASS_FIRST_PROOF_COMMAND_CENTER_READY_READONLY"
    assert d["ui_submit_enabled"] is False and d["ui_writes_enabled"] is False
    assert d["safe_mode"] == "READ_ONLY_FAIL_CLOSED"
    assert d["execute_once_command"].startswith("DUMMY_LIVE_PROOF_MODE=1")
    _safe(d)


# --- V251 pre-execution freeze (blocked by missing authority) ---
def test_v251_default_blocked_and_fixture_ready() -> None:
    d = generate_all_v251_reports_for_tests()["v251_pre_execution_freeze_controller_report.json"]
    assert d["pre_execution_freeze_controller_status"] == "PARTIAL_PRE_EXECUTION_FREEZE_BLOCKED_BY_MISSING_AUTHORITY"
    assert d["resolver_state"] == "LIVE_BLOCKED_AUTHORITY_ABSENT"
    ok = generate_all_v251_reports_for_tests(armable_override=True, manifest_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK)["v251_pre_execution_freeze_controller_report.json"]
    assert ok["pre_execution_freeze_controller_status"] == "PASS_PRE_EXECUTION_FREEZE_READY_NO_SUBMIT"
    assert ok["resolver_state"] == "LIVE_PROOF_ARMABLE" and ok["total_real_live_orders_submitted"] == 0
    _safe(ok)


# --- V252 execute-once dry/fixture harness V3 (safety proven) ---
def test_v252_default_dry_and_fixture_proven_safe() -> None:
    d = generate_all_v252_reports_for_tests()["v252_execute_once_dry_fixture_harness_controller_report.json"]
    assert d["execute_once_dry_fixture_harness_controller_status"] == "PARTIAL_EXECUTE_ONCE_DRY_FIXTURE_HARNESS_NOT_ARMED_REAL"
    assert d["dry_run_default"] is True and d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v252_reports_for_tests(
        proof_approval=pilot_approval(), armable_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK,
        mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True,
        caps_config_present=True, firewall_adapter=FakeFirewall("v252-attempt-1"),
    )["v252_execute_once_dry_fixture_harness_controller_report.json"]
    assert c["execute_once_dry_fixture_harness_controller_status"] == "PASS_EXECUTE_ONCE_DRY_FIXTURE_HARNESS_PROVEN_SAFE"
    assert c["order_attempt_id"] == "v252-attempt-1" and c["proof_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    _safe(c)


def test_v252_blocks_missing_env_authority_fuzzy_and_no_adapter() -> None:
    base = dict(proof_approval=pilot_approval(), armable_override=True, env_gate_mode=True, env_gate_ack=LIVE_PROOF_ACK,
                mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))
    ctrl = "v252_execute_once_dry_fixture_harness_controller_report.json"
    for key, val in [("env_gate_mode", False), ("armable_override", False), ("proof_approval", pilot_approval("bad")), ("firewall_adapter", None)]:
        r = generate_all_v252_reports_for_tests(**{**base, key: val})[ctrl]
        assert r["firewall_submit_invoked"] is False and r["live_orders"] == 0


# --- V253 post-execution intake bridge (default no attempt) ---
def test_v253_default_no_attempt_and_override_ready() -> None:
    d = generate_all_v253_reports_for_tests()["v253_post_execution_intake_bridge_controller_report.json"]
    assert d["post_execution_intake_bridge_controller_status"] == "PARTIAL_NO_EXECUTION_ATTEMPT_TO_INGEST"
    assert d["bridge_state"] == "NO_ATTEMPT"
    r = generate_all_v253_reports_for_tests(
        v252_final_override={"execute_once_dry_fixture_harness_controller_status": "PASS_EXECUTE_ONCE_DRY_FIXTURE_HARNESS_PROVEN_SAFE", "simulated_order_submits_count": 1, "proof_target": "FIRST_REAL_PILOT_PROOF"})["v253_post_execution_intake_bridge_controller_report.json"]
    assert r["post_execution_intake_bridge_controller_status"] == "PASS_POST_EXECUTION_INTAKE_BRIDGE_READY_LOCKED"
    assert r["bridge_state"] == "ATTEMPT_READY_FOR_RECONCILE" and r["new_order_placed"] is False
    _safe(r)


# --- V254 completion lift V5 (fixtures never inflate real proof) ---
def test_v254_completion_lift_no_fixture_inflation() -> None:
    d = generate_all_v254_reports_for_tests()["v254_completion_lift_v5_controller_report.json"]
    assert d["completion_lift_v5_controller_status"] == "PASS_COMPLETION_LIFT_V5_OPERATOR_READY_LOCKED"
    assert d["subsystem_percentages"]["first_live_proof"] == 0
    assert d["real_first_live_proof_present"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    assert d["scale_autonomy_blocked_by_no_live_proof"] is True
    assert d["subsystem_percentages"]["scale_review"] == 0 and d["subsystem_percentages"]["autonomy_review"] == 0
    _safe(d)


# --- safety / locks / no-runtime-approvals default across the whole bundle ---
def test_v245_to_v254_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v245_reports_for_tests, generate_all_v246_reports_for_tests, generate_all_v247_reports_for_tests,
        generate_all_v248_reports_for_tests, generate_all_v249_reports_for_tests, generate_all_v250_reports_for_tests,
        generate_all_v251_reports_for_tests, generate_all_v252_reports_for_tests, generate_all_v253_reports_for_tests,
        generate_all_v254_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            _safe(report)


# --- Dummy never creates runtime/approvals during generation ---
def test_dummy_does_not_create_runtime_approvals() -> None:
    existed_before = (ROOT / "runtime" / "approvals").exists()
    for gen in (generate_all_v247_reports_for_tests, generate_all_v249_reports_for_tests, generate_all_v252_reports_for_tests):
        gen()
    assert (ROOT / "runtime" / "approvals").exists() == existed_before
