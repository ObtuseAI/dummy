from __future__ import annotations

from tests.v51_test_helpers import assert_v51_report_named


def test_v51_v50_baseline_readback_preserves_locked_preflight_authority() -> None:
    report = assert_v51_report_named("v50_baseline_readback_v1_report.json", "v50_baseline_status")
    assert report["v50_baseline_status"] == "PASS_V50_BASELINE_READBACK"
    assert report["v50_final_verdict"] == "PASS"
    assert report["v49_baseline_status"] == "PASS_V49_BASELINE_READBACK"
    assert report["v49_cumulative_real_scored_count"] == 144
    assert report["v50_new_real_scored_count"] == 18
    assert report["v50_cumulative_real_scored_count"] == 162
    assert report["v50_locked_rehearsal_preflight_status"] == "PASS_LOCKED_REHEARSAL_PREFLIGHT_READONLY"
    assert report["v50_rehearsal_gate_lock_contract_status"] == "PASS_REHEARSAL_GATE_LOCK_CONTRACT_READONLY"
    assert report["v50_nonexecution_validator_v2_status"] == "PASS_NONEXECUTION_VALIDATOR_V2"
    assert report["v50_holdout_status"] == "PASS_STABLE_SAMPLE_HOLDOUT_CONTINUATION_READONLY"
    assert report["v50_readiness_governor_v10_status"] == "PASS"
    assert report["v50_execution_lock_v9_status"] == "PASS"


def test_v51_approval_surface_is_locked_and_policy_only() -> None:
    report = assert_v51_report_named("v51_approval_surface_controller_report.json", "approval_surface_status", enabled=True)
    assert report["approval_surface_status"] == "PASS_APPROVAL_SURFACE_LOCKED"
    assert report["approval_surface_mode"] == "INERT_POLICY_CONFIG_VALIDATION_ONLY"
    assert report["approval_surface_can_unlock_rehearsal"] is False
    assert report["approval_surface_created_rehearsal_packet"] is False
    assert report["approval_surface_created_execution_artifact"] is False
    assert report["v51_execution_artifacts_created"] is False


def test_v51_rehearsal_approval_policy_defines_future_requirements_only() -> None:
    report = assert_v51_report_named("v51_rehearsal_approval_policy_report.json", "rehearsal_approval_policy_status", enabled=True)
    assert report["rehearsal_approval_policy_status"] == "PASS_REHEARSAL_APPROVAL_POLICY_LOCKED"
    assert report["future_rehearsal_approval_phrase_required"] is True
    assert report["operator_identity_required"] is True
    assert report["operator_timestamp_required"] is True
    assert report["operator_reason_required"] is True
    assert report["config_preconditions_required"] is True
    assert report["caps_ownership_proof_required"] is True
    assert report["live_submit_disabled_proof_required"] is True
    assert report["firewall_only_design_proof_required"] is True
    assert report["no_market_order_proof_required"] is True
    assert report["kill_switch_proof_required"] is True
    assert report["rollback_proof_required"] is True
    assert report["audit_ledger_proof_required"] is True
    assert report["policy_created_executable_rehearsal"] is False


def test_v51_holdout_and_governors_stay_locked() -> None:
    holdout = assert_v51_report_named("v51_holdout_continuation_report.json", "holdout_continuation_status", enabled=True)
    assert holdout["holdout_continuation_status"] == "PASS_HOLDOUT_CONTINUATION_READONLY"
    assert holdout["v51_new_real_scored_count"] == 18
    assert holdout["cumulative_real_scored_count"] == 180
    assert holdout["max_total_requests"] == 24
    assert holdout["per_request_timeout_seconds"] == 12
    assert holdout["sports_excluded"] is True
    assert holdout["fake_fixture_stale_duplicate_rejected"] is True
    readiness = assert_v51_report_named("readiness_governor_v11_report.json", "readiness_governor_v11_status", enabled=True)
    assert readiness["readiness_governor_v11_status"] == "PASS"
    assert readiness["READONLY_APPROVAL_SURFACE_REVIEW"] == "ACHIEVED"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    assert readiness["current_next_action"] == "OPERATOR_APPROVAL_REQUIRED_FOR_REHEARSAL_ARTIFACTS"
    lock = assert_v51_report_named("execution_lock_deep_recheck_v10_report.json", "execution_lock_deep_recheck_v10_status", enabled=True)
    assert lock["execution_lock_deep_recheck_v10_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["selected_action_can_trigger_execution"] is False
