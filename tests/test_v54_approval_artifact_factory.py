from __future__ import annotations

import json

from tests.v54_test_helpers import VALID_PHRASE, approval_input, assert_v54_report_named, v54_enabled_reports, v54_reports


def test_v54_reads_v53_partial_baseline_and_defaults_to_partial_without_dedicated_approval() -> None:
    report = assert_v54_report_named("v54_exact_approval_controller_report.json", "approval_controller_status")
    assert report["v53_baseline_status"] == "PASS_V53_BASELINE_READBACK"
    assert report["v53_final_verdict"] == "PARTIAL"
    assert report["v53_new_real_scored_count"] == 12
    assert report["v53_cumulative_real_scored_count"] == 210
    assert report["approval_controller_status"] == "PARTIAL_APPROVAL_INPUT_ABSENT"
    assert report["prompt_text_treated_as_approval"] is False
    assert report["dedicated_v54_approval_input_present"] is False
    assert report["approval_validated"] is False
    assert report["created_quarantine_artifact_count"] == 0
    final = v54_reports()["final_report_v54.json"]
    assert final["verdict"] == "PARTIAL"
    assert "APPROVAL_INPUT_ABSENT" in final["current_blockers"]
    assert final["current_next_action"] == "AWAIT_EXPLICIT_REHEARSAL_ARTIFACT_APPROVAL"


def test_v54_exact_approval_creates_only_allowed_inert_quarantine_artifacts(tmp_path) -> None:
    reports = v54_enabled_reports(approval_input=approval_input(), write_quarantine_artifacts=True, quarantine_dir=tmp_path)
    controller = reports["v54_exact_approval_controller_report.json"]
    factory = reports["v54_inert_quarantine_artifact_factory_report.json"]
    final = reports["final_report_v54.json"]
    assert controller["approval_controller_status"] == "PASS_EXACT_APPROVAL_ACCEPTED_FOR_INERT_QUARANTINE_ONLY"
    assert factory["artifact_factory_status"] == "PASS_INERT_QUARANTINE_ARTIFACTS_CREATED"
    assert factory["created_quarantine_artifact_count"] == 4
    assert factory["created_artifact_types"] == [
        "REHEARSAL_PLAN_DRAFT",
        "REHEARSAL_RISK_CHECKLIST",
        "REHEARSAL_VALIDATION_CHECKLIST",
        "REHEARSAL_AUDIT_TEMPLATE",
    ]
    assert final["verdict"] == "PASS"
    assert final["current_next_action"] == "QUARANTINED_REHEARSAL_ARTIFACTS_CREATED_RELEASE_LOCKED"

    files = sorted(tmp_path.glob("*.json"))
    assert len(files) == 4
    forbidden_fields = {"market_id", "account", "balance", "position", "size", "quantity", "price", "side", "submit_endpoint", "cancel_endpoint", "command", "broker_payload", "order"}
    for path in files:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        assert artifact["artifact_type"] in factory["created_artifact_types"]
        assert artifact["approval_hash"] == controller["approval_hash"]
        assert artifact["operator"] == "operator:chris"
        assert artifact["inert_only"] is True
        assert artifact["no_broker_payload"] is True
        assert artifact["no_order_submission"] is True
        assert artifact["no_live_trading"] is True
        assert artifact["no_live_submit"] is True
        assert artifact["no_caps_modification"] is True
        assert artifact["quarantine_release_locked"] is True
        assert forbidden_fields.isdisjoint(artifact)


def test_v54_fuzzy_broad_or_live_approval_fails_closed_and_creates_no_artifacts(tmp_path) -> None:
    fuzzy = approval_input("I approve Dummy to create rehearsal artifacts")
    reports = v54_reports(approval_input=fuzzy, write_quarantine_artifacts=True, quarantine_dir=tmp_path)
    controller = reports["v54_exact_approval_controller_report.json"]
    factory = reports["v54_inert_quarantine_artifact_factory_report.json"]
    assert controller["approval_controller_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert controller["approval_validated"] is False
    assert "APPROVAL_PHRASE_NOT_EXACT" in controller["approval_result"]["blockers"]
    assert factory["artifact_factory_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert factory["created_quarantine_artifact_count"] == 0
    assert not list(tmp_path.glob("*.json"))

    live = approval_input(VALID_PHRASE + " and submit orders")
    assert v54_reports(approval_input=live)["v54_exact_approval_controller_report.json"]["approval_controller_status"] == "FAIL_CLOSED_INVALID_APPROVAL"


def test_v54_quarantine_release_lock_canary_readiness_and_execution_lock() -> None:
    release = assert_v54_report_named("v54_quarantine_release_lock_report.json", "quarantine_release_lock_status", enabled=True, approval=approval_input())
    assert release["quarantine_release_lock_status"] == "PASS_QUARANTINE_RELEASE_LOCKED"
    assert release["quarantine_release_path_present"] is False
    assert release["quarantine_to_execution_transform_status"] == "FAIL_CLOSED_NO_TRANSFORM_PATH"

    canary = assert_v54_report_named("v54_canary_nonexecution_validator_v4_report.json", "canary_nonexecution_validator_v4_status", enabled=True, approval=approval_input())
    assert canary["canary_nonexecution_validator_v4_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR_V4"
    assert canary["order_cancel_reference_detected"] is False
    assert canary["broker_payload_reference_detected"] is False
    assert canary["quarantine_release_path_reference_detected"] is False
    assert canary["capital_or_portfolio_reference_detected"] is False
    assert canary["account_private_access_reference_detected"] is False

    readiness = assert_v54_report_named("readiness_governor_v14_report.json", "readiness_governor_v14_status", enabled=True, approval=approval_input())
    assert readiness["readiness_governor_v14_status"] == "PASS"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    assert readiness["current_next_action"] == "QUARANTINED_REHEARSAL_ARTIFACTS_CREATED_RELEASE_LOCKED"

    lock = assert_v54_report_named("execution_lock_deep_recheck_v13_report.json", "execution_lock_deep_recheck_v13_status", enabled=True, approval=approval_input())
    assert lock["execution_lock_deep_recheck_v13_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["selected_action_can_trigger_execution"] is False
