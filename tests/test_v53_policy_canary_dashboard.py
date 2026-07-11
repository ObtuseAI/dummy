from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from archive.routes.v53_routes import router
from predator_mesh.v53.reports import ALLOWED_REHEARSAL_ARTIFACT_TYPES, DENIED_REHEARSAL_ARTIFACT_TYPES, SAFETY_REPORT_NAMES
from tests.v53_test_helpers import ApprovalIntakeReadOnlyTransport, approval_input, assert_v53_report_named, v53_reports


def test_v53_quarantine_manifest_dry_policy_and_allowlist_are_inert() -> None:
    manifest = assert_v53_report_named("v53_quarantine_manifest_dry_policy_report.json", "quarantine_manifest_dry_policy_status", enabled=True)
    assert manifest["quarantine_manifest_dry_policy_status"] == "PASS_QUARANTINE_MANIFEST_DRY_POLICY_ONLY"
    assert manifest["manifest_schema_fields"] == [
        "artifact_id",
        "created_at",
        "operator_approval_hash",
        "artifact_type",
        "reason",
        "scope",
        "expiration",
        "no_broker_payload",
        "no_live_submit",
        "no_caps_modification",
        "no_order_submission",
    ]
    assert manifest["manifest_instances_created"] == 0
    assert manifest["schema_defaults"]["no_broker_payload"] is True
    assert manifest["schema_defaults"]["no_live_submit"] is True
    allowlist = assert_v53_report_named("v53_rehearsal_artifact_allowlist_report.json", "artifact_allowlist_status", enabled=True)
    assert allowlist["artifact_allowlist_status"] == "PASS_REHEARSAL_ARTIFACT_ALLOWLIST_LOCKED"
    assert allowlist["allowed_artifact_types"] == ALLOWED_REHEARSAL_ARTIFACT_TYPES
    assert "broker payload" in DENIED_REHEARSAL_ARTIFACT_TYPES
    assert allowlist["denied_artifact_types"] == DENIED_REHEARSAL_ARTIFACT_TYPES
    assert allowlist["denylist_enforced"] is True


def test_v53_canary_v3_safety_reports_and_holdout_are_read_only() -> None:
    holdout = assert_v53_report_named("v53_holdout_continuation_report.json", "holdout_continuation_status", enabled=True)
    assert holdout["holdout_continuation_status"] == "PASS_HOLDOUT_CONTINUATION_READONLY"
    assert holdout["v53_new_real_scored_count"] == 12
    assert holdout["max_new_real_scored_count"] == 12
    assert holdout["max_total_requests"] == 16
    assert holdout["per_request_timeout_seconds"] == 12
    assert holdout["sports_excluded"] is True
    validator = assert_v53_report_named("v53_canary_nonexecution_validator_v3_report.json", "canary_nonexecution_validator_v3_status", enabled=True)
    assert validator["canary_nonexecution_validator_v3_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR_V3"
    assert validator["order_cancel_reference_detected"] is False
    assert validator["order_ticket_reference_detected"] is False
    assert validator["shadow_order_reference_detected"] is False
    assert validator["dry_submit_packet_reference_detected"] is False
    assert validator["broker_payload_reference_detected"] is False
    assert validator["executable_rehearsal_reference_detected"] is False
    assert validator["broker_schema_reference_detected"] is False
    assert validator["order_intent_reference_detected"] is False
    assert validator["capital_or_portfolio_reference_detected"] is False
    assert validator["account_private_access_reference_detected"] is False
    assert validator["live_submit_caps_mutation_reference_detected"] is False
    for name in SAFETY_REPORT_NAMES:
        report = assert_v53_report_named(name, "safety_status", enabled=True)
        assert report["safety_status"] == "PASS"
        assert report["v53_execution_artifacts_created"] is False
        assert report["quarantine_manifest_instances_created"] is False


def test_v53_exact_gate_fuzzy_ack_readiness_execution_and_dashboard() -> None:
    fuzzy = v53_reports(
        env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY submit broker"},
        enable_real_probe=True,
        real_transport=ApprovalIntakeReadOnlyTransport(),
    )["exact_gate_runtime_v21_report.json"]
    assert fuzzy["ack_decision"] == "FAIL_FUZZY_ACK"
    assert fuzzy["v53_new_real_probe_count"] == 0
    assert fuzzy["trading_language_rejected"] is True
    readiness = assert_v53_report_named("readiness_governor_v13_report.json", "readiness_governor_v13_status", enabled=True)
    assert readiness["readiness_governor_v13_status"] == "PASS"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    lock = assert_v53_report_named("execution_lock_deep_recheck_v12_report.json", "execution_lock_deep_recheck_v12_status", enabled=True)
    assert lock["execution_lock_deep_recheck_v12_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["selected_action_can_trigger_execution"] is False
    approved_readiness = assert_v53_report_named("readiness_governor_v13_report.json", enabled=True, approval=approval_input())
    assert approved_readiness["current_next_action"] == "APPROVAL_VALIDATED_FOR_FUTURE_QUARANTINE_ONLY"
    dashboard = assert_v53_report_named("dashboard_v53_report_v1.json", "dashboard_status")
    assert "/api/v53/approval-intake" in dashboard["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v53/approval-intake")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert "v53_approval_intake_controller_report" in payload
