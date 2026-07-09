from __future__ import annotations

from tests.v49_test_helpers import assert_v49_report_named


def test_v49_v48_baseline_readback_preserves_locked_design_authority() -> None:
    report = assert_v49_report_named("v48_baseline_readback_v1_report.json", "v48_baseline_status")
    assert report["v48_baseline_status"] == "PASS_V48_BASELINE_READBACK"
    assert report["v48_final_verdict"] == "PASS"
    assert report["v47_baseline_real_scored_count"] == 108
    assert report["v48_new_real_scored_count"] == 18
    assert report["v48_cumulative_real_scored_count"] == 126
    assert report["v48_stable_sample_review_verdict"] == "PASS_STABLE_SAMPLE_REVIEW_READONLY"
    assert report["v48_locked_rehearsal_gate_design_status"] == "PASS_LOCKED_DESIGN_ONLY"
    assert report["v48_readiness_governor_v8_status"] == "PASS"
    assert report["v48_execution_lock_v7_status"] == "PASS"


def test_v49_stable_sample_holdout_audit_is_readonly_and_bounded() -> None:
    report = assert_v49_report_named("v49_stable_sample_holdout_audit_report.json", "stable_sample_holdout_status", enabled=True)
    assert report["stable_sample_holdout_status"] == "PASS_STABLE_SAMPLE_HOLDOUT_READONLY"
    assert report["v49_new_real_scored_count"] == 18
    assert report["cumulative_real_scored_count"] == 144
    assert report["source_concentration_review_status"] == "PASS"
    assert report["lane_concentration_review_status"] == "PASS"
    assert report["market_class_concentration_review_status"] == "PASS"
    assert report["metric_cluster_review_status"] == "PASS"
    assert report["temporal_spread_review_status"] == "PASS"
    assert report["duplicate_stale_leakage_status"] == "PASS_NONE_DETECTED"
    assert report["settlement_ambiguity_leakage_status"] == "PASS_NONE_DETECTED"
    assert report["not_due_unresolved_leakage_status"] == "PASS_NONE_DETECTED"
    assert report["max_observer_lanes"] == 4
    assert report["max_cycles_per_lane"] == 2
    assert report["max_total_requests"] == 24
    assert report["per_request_timeout_seconds"] == 12
    assert report["sports_excluded"] is True


def test_v49_locked_rehearsal_gate_review_remains_design_only() -> None:
    report = assert_v49_report_named("v49_locked_rehearsal_gate_spec_review_report.json", "locked_rehearsal_gate_review_status", enabled=True)
    assert report["locked_rehearsal_gate_review_status"] == "PASS_LOCKED_REHEARSAL_GATE_REVIEW_ONLY"
    assert report["future_operator_approval_phrase_required"] is True
    assert report["future_config_prerequisites_required"] is True
    assert report["future_live_broker_firewall_submit_only_path_required"] is True
    assert report["future_limit_order_only_rule_required"] is True
    assert report["future_no_market_order_rule_required"] is True
    assert report["future_cancel_reconcile_proof_required"] is True
    assert report["future_idempotency_proof_required"] is True
    assert report["future_liquidity_slippage_proof_required"] is True
    assert report["future_kill_switch_required"] is True
    assert report["future_fail_closed_behavior_required"] is True
    assert report["v49_rehearsal_artifacts_created"] is False
    assert report["execution_bridge_present"] is False


def test_v49_readiness_governor_and_execution_lock_stay_locked() -> None:
    readiness = assert_v49_report_named("readiness_governor_v9_report.json", "readiness_governor_v9_status", enabled=True)
    assert readiness["readiness_governor_v9_status"] == "PASS"
    assert readiness["READONLY_STABLE_SAMPLE_REVIEW"] == "ACHIEVED"
    assert readiness["READONLY_REHEARSAL_GATE_DESIGN_REVIEW"] == "ACHIEVED"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    lock = assert_v49_report_named("execution_lock_deep_recheck_v8_report.json", "execution_lock_deep_recheck_v8_status", enabled=True)
    assert lock["execution_lock_deep_recheck_v8_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["selected_action_can_trigger_execution"] is False
