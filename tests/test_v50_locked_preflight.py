from __future__ import annotations

from tests.v50_test_helpers import assert_v50_report_named


def test_v50_v49_baseline_readback_preserves_operator_armed_lock_authority() -> None:
    report = assert_v50_report_named("v49_baseline_readback_v1_report.json", "v49_baseline_status")
    assert report["v49_baseline_status"] == "PASS_V49_BASELINE_READBACK"
    assert report["v49_final_verdict"] == "PASS"
    assert report["v48_baseline_status"] == "PASS_V48_BASELINE_READBACK"
    assert report["v49_new_real_scored_count"] == 18
    assert report["v49_cumulative_real_scored_count"] == 144
    assert report["v49_stable_sample_holdout_status"] == "PASS_STABLE_SAMPLE_HOLDOUT_READONLY"
    assert report["v49_locked_rehearsal_gate_review_status"] == "PASS_LOCKED_REHEARSAL_GATE_REVIEW_ONLY"
    assert report["v49_nonexecution_validator_status"] == "PASS_NONEXECUTION_VALIDATOR"
    assert report["v49_readiness_governor_v9_status"] == "PASS"
    assert report["v49_execution_lock_v8_status"] == "PASS"
    assert report["v49_next_action"] == "OPERATOR_ARMED_REHEARSAL_LOCKED"


def test_v50_locked_preflight_is_readonly_and_nonexecutable() -> None:
    report = assert_v50_report_named("v50_locked_rehearsal_preflight_controller_report.json", "locked_rehearsal_preflight_status", enabled=True)
    assert report["locked_rehearsal_preflight_status"] == "PASS_LOCKED_REHEARSAL_PREFLIGHT_READONLY"
    assert report["preflight_output_mode"] == "INERT_REVIEW_ARTIFACTS_ONLY"
    assert report["future_operator_armed_rehearsal_locked"] is True
    assert report["preflight_can_trigger_rehearsal"] is False
    assert report["preflight_can_create_order_intent"] is False
    assert report["v50_execution_artifacts_created"] is False


def test_v50_rehearsal_gate_lock_contract_is_nonexecutable() -> None:
    report = assert_v50_report_named("v50_rehearsal_gate_lock_contract_report.json", "rehearsal_gate_lock_contract_status", enabled=True)
    assert report["rehearsal_gate_lock_contract_status"] == "PASS_REHEARSAL_GATE_LOCK_CONTRACT_READONLY"
    assert report["future_operator_approval_phrase_required"] is True
    assert report["future_config_approval_required"] is True
    assert report["live_submit_separate_approval_required"] is True
    assert report["caps_operator_owned_required"] is True
    assert report["future_live_broker_firewall_only_required"] is True
    assert report["future_limit_order_only_rule_required"] is True
    assert report["future_no_market_order_rule_required"] is True
    assert report["future_kill_switch_required"] is True
    assert report["future_cancel_reconcile_proof_required"] is True
    assert report["future_idempotency_proof_required"] is True
    assert report["future_slippage_liquidity_proof_required"] is True
    assert report["future_rollback_proof_required"] is True
    assert report["future_fail_closed_proof_required"] is True
    assert report["contract_created_runnable_code"] is False


def test_v50_holdout_continuation_and_governors_stay_locked() -> None:
    holdout = assert_v50_report_named("v50_stable_sample_holdout_continuation_report.json", "stable_sample_holdout_continuation_status", enabled=True)
    assert holdout["stable_sample_holdout_continuation_status"] == "PASS_STABLE_SAMPLE_HOLDOUT_CONTINUATION_READONLY"
    assert holdout["v50_new_real_scored_count"] == 18
    assert holdout["cumulative_real_scored_count"] == 162
    assert holdout["max_observer_lanes"] == 4
    assert holdout["max_cycles_per_lane"] == 2
    assert holdout["max_total_requests"] == 24
    assert holdout["per_request_timeout_seconds"] == 12
    assert holdout["sports_excluded"] is True
    readiness = assert_v50_report_named("readiness_governor_v10_report.json", "readiness_governor_v10_status", enabled=True)
    assert readiness["readiness_governor_v10_status"] == "PASS"
    assert readiness["READONLY_REHEARSAL_GATE_PREFLIGHT"] == "ACHIEVED"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    lock = assert_v50_report_named("execution_lock_deep_recheck_v9_report.json", "execution_lock_deep_recheck_v9_status", enabled=True)
    assert lock["execution_lock_deep_recheck_v9_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["selected_action_can_trigger_execution"] is False
