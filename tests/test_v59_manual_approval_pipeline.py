from __future__ import annotations

import json

from predator_mesh.v55.reports import DEFAULT_APPROVAL_INPUT_PATH
from predator_mesh.v59.reports import DENIAL_KINDS, deny, release_denial_matrix, validate_artifact_integrity
from tests.v59_test_helpers import (
    VALID_PHRASE,
    approval_input,
    assert_v59_report_named,
    v59_reports,
    write_approval_file,
)


def test_v59_reads_v58_baseline_and_defaults_partial_without_approval_file() -> None:
    report = assert_v59_report_named("v59_manual_approval_pipeline_controller_report.json", "manual_approval_pipeline_controller_status")
    assert report["v58_baseline_status"] == "PASS_V58_BASELINE_READBACK"
    assert report["v58_release_denial_proof_status"] == "PASS_RELEASE_DENIED"
    assert report["v58_cumulative_real_scored_count"] == 222
    assert report["manual_approval_pipeline_controller_status"] == "PARTIAL_MANUAL_APPROVAL_FILE_ABSENT"
    assert report["dummy_creates_approval_file"] is False
    assert report["dummy_auto_fills_approval_file"] is False
    assert report["created_quarantine_instance_count"] == 0
    final = v59_reports()["final_report_v59.json"]
    assert final["verdict"] == "PARTIAL"
    assert "MANUAL_APPROVAL_FILE_ABSENT" in final["current_blockers"]
    assert final["current_next_action"] == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"


def test_v59_malformed_approval_returns_partial_malformed(tmp_path) -> None:
    path = write_approval_file(tmp_path, "{ not json ]")
    reports = v59_reports(approval_path=path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "q")
    controller = reports["v59_manual_approval_pipeline_controller_report.json"]
    factory = reports["v59_inert_quarantine_artifact_factory_v3_report.json"]
    assert controller["manual_approval_pipeline_controller_status"] == "PARTIAL_MANUAL_APPROVAL_FILE_MALFORMED"
    assert factory["inert_quarantine_artifact_factory_v3_status"] == "PARTIAL_MANUAL_APPROVAL_FILE_MALFORMED_NO_INSTANCES_CREATED"
    assert factory["created_quarantine_instance_count"] == 0
    assert reports["readiness_governor_v19_report.json"]["current_next_action"] == "APPROVAL_REPAIR_REQUIRED"


def test_v59_fuzzy_or_live_approval_fails_closed(tmp_path) -> None:
    fuzzy_path = write_approval_file(tmp_path / "a", approval_input("I approve Dummy to create rehearsal artifacts"))
    controller = v59_reports(approval_path=fuzzy_path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "qa")["v59_manual_approval_pipeline_controller_report.json"]
    assert controller["manual_approval_pipeline_controller_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert controller["approval_validated"] is False
    assert not (tmp_path / "qa").exists() or not list((tmp_path / "qa").glob("*.json"))

    live_path = write_approval_file(tmp_path / "b", approval_input(VALID_PHRASE + " and submit orders"))
    live = v59_reports(approval_path=live_path)["v59_manual_approval_pipeline_controller_report.json"]
    assert live["manual_approval_pipeline_controller_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert "LIVE_OR_BROAD_EXECUTION_LANGUAGE_REJECTED" in live["approval_result"]["blockers"]


def test_v59_exact_approval_full_pipeline_creates_reviews_and_denies_release(tmp_path) -> None:
    approval_dir = tmp_path / "approvals"
    quarantine_dir = tmp_path / "quarantine"
    path = write_approval_file(approval_dir, approval_input())
    reports = v59_reports(approval_path=path, write_quarantine_artifacts=True, quarantine_dir=quarantine_dir)
    controller = reports["v59_manual_approval_pipeline_controller_report.json"]
    factory = reports["v59_inert_quarantine_artifact_factory_v3_report.json"]
    review = reports["v59_artifact_integrity_review_v2_report.json"]
    denial = reports["v59_release_denial_v2_report.json"]
    final = reports["final_report_v59.json"]

    assert controller["manual_approval_pipeline_controller_status"] == "PASS_MANUAL_APPROVAL_ACCEPTED_INERT_PIPELINE_ONLY"
    assert factory["inert_quarantine_artifact_factory_v3_status"] == "PASS_INERT_QUARANTINE_INSTANCES_CREATED"
    assert factory["created_quarantine_instance_count"] == 4
    assert factory["created_artifact_types"] == [
        "REHEARSAL_PLAN_DRAFT",
        "REHEARSAL_RISK_CHECKLIST",
        "REHEARSAL_VALIDATION_CHECKLIST",
        "REHEARSAL_AUDIT_TEMPLATE",
    ]
    assert review["v59_artifact_integrity_review_v2_status"] == "PASS_ARTIFACT_INTEGRITY_VALIDATED"
    assert review["no_mutation_during_review"] is True
    assert all(entry["unchanged"] for entry in review["cases"])
    assert denial["v59_release_denial_v2_status"] == "PASS_RELEASE_DENIED"
    assert final["verdict"] == "PASS"
    assert final["current_next_action"] == "QUARANTINED_REHEARSAL_ARTIFACTS_CREATED_AND_REVIEWED_RELEASE_LOCKED"

    files = sorted(quarantine_dir.glob("*.json"))
    assert len(files) == 4
    forbidden_fields = {
        "order_id",
        "market_order",
        "market_id",
        "side",
        "quantity",
        "price",
        "submit",
        "cancel",
        "broker_payload",
        "order_intent",
        "position_size",
        "capital_allocation",
        "portfolio_weight",
        "account_balance",
        "private_position",
        "executable_command",
        "endpoint",
        "credential",
        "api_key",
        "private_key",
    }
    for artifact_path in files:
        instance = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert instance["artifact_type"] in factory["created_artifact_types"]
        assert instance["approval_hash"] == controller["approval_hash"]
        assert instance["inert_only"] is True
        assert instance["execution_bridge_present"] is False
        assert instance["quarantine_release_locked"] is True
        assert forbidden_fields.isdisjoint(instance)

    # Dummy never creates the real dedicated approval file.
    assert not DEFAULT_APPROVAL_INPUT_PATH.exists()


def test_v59_integrity_review_rejects_forbidden_fields() -> None:
    tampered = {
        "artifact_type": "REHEARSAL_PLAN_DRAFT",
        "artifact_id": "x",
        "approval_hash": "abc",
        "inert_only": True,
        "no_broker_payload": True,
        "no_order_submission": True,
        "no_live_trading": True,
        "no_live_submit": True,
        "no_caps_modification": True,
        "quarantine_release_locked": True,
        "execution_bridge_present": False,
        "broker_payload": {"order_id": "X"},
        "api_key": "secret",
    }
    result = validate_artifact_integrity(tampered)
    assert result["integrity_pass"] is False
    assert "broker_payload" in result["forbidden_fields_present"]
    assert "api_key" in result["forbidden_fields_present"]


def test_v59_release_denial_matrix_all_fail_closed() -> None:
    matrix = release_denial_matrix()
    assert {entry["kind"] for entry in matrix} == set(DENIAL_KINDS)
    for entry in matrix:
        assert entry["status"] == "FAIL_CLOSED_DENIED"
        assert entry["released"] is False
        assert entry["side_effect"] is False
    assert deny("quarantine_release")["released"] is False


def test_v59_canary_readiness_and_execution_lock(tmp_path) -> None:
    path = write_approval_file(tmp_path, approval_input())
    quarantine_dir = tmp_path / "q"

    canary = assert_v59_report_named("v59_canary_nonexecution_validator_v9_report.json", "canary_nonexecution_validator_v9_status", approval_path=path, write_quarantine_artifacts=True, quarantine_dir=quarantine_dir)
    assert canary["canary_nonexecution_validator_v9_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR_V9"
    assert canary["order_cancel_reference_detected"] is False
    assert canary["transform_to_broker_path_reference_detected"] is False
    assert canary["browser_pageagent_dom_reference_detected"] is False
    assert canary["sports_activation_reference_detected"] is False

    readiness = assert_v59_report_named("readiness_governor_v19_report.json", "readiness_governor_v19_status", approval_path=path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "q2")
    assert readiness["readiness_governor_v19_status"] == "PASS"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    assert readiness["current_next_action"] == "QUARANTINED_REHEARSAL_ARTIFACTS_CREATED_AND_REVIEWED_RELEASE_LOCKED"

    lock = assert_v59_report_named("execution_lock_deep_recheck_v18_report.json", "execution_lock_deep_recheck_v18_status", approval_path=path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "q3")
    assert lock["execution_lock_deep_recheck_v18_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["unauthorized_artifact_mutation"] is False


def test_v59_default_readiness_awaits_manual_file() -> None:
    readiness = assert_v59_report_named("readiness_governor_v19_report.json", "current_next_action")
    assert readiness["current_next_action"] == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True


def test_v59_default_creates_no_approval_file() -> None:
    v59_reports()
    assert not DEFAULT_APPROVAL_INPUT_PATH.exists()
