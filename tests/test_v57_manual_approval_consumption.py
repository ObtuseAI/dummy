from __future__ import annotations

import json

from predator_mesh.v57.reports import DEFAULT_APPROVAL_INPUT_PATH
from tests.v57_test_helpers import (
    VALID_PHRASE,
    approval_input,
    assert_v57_report_named,
    v57_reports,
    write_approval_file,
)


def test_v57_reads_v56_baseline_and_defaults_partial_without_approval_file() -> None:
    report = assert_v57_report_named("v57_manual_approval_file_consumer_report.json", "manual_approval_file_consumer_status")
    assert report["v56_baseline_status"] == "PASS_V56_BASELINE_READBACK"
    assert report["v56_operator_handoff_status"] == "PASS_OPERATOR_HANDOFF_READY"
    assert report["v56_cumulative_real_scored_count"] == 222
    assert report["manual_approval_file_consumer_status"] == "PARTIAL_APPROVAL_FILE_ABSENT"
    assert report["dummy_creates_approval_file"] is False
    assert report["dummy_modifies_approval_file"] is False
    assert report["created_quarantine_instance_count"] == 0
    final = v57_reports()["final_report_v57.json"]
    assert final["verdict"] == "PARTIAL"
    assert "APPROVAL_FILE_ABSENT" in final["current_blockers"]
    assert final["current_next_action"] == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"


def test_v57_absent_approval_creates_zero_instances(tmp_path) -> None:
    missing = tmp_path / "nope.json"
    reports = v57_reports(approval_path=missing, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "q")
    consumer = reports["v57_manual_approval_file_consumer_report.json"]
    factory = reports["v57_inert_quarantine_instance_factory_v2_report.json"]
    assert consumer["manual_approval_file_consumer_status"] == "PARTIAL_APPROVAL_FILE_ABSENT"
    assert factory["inert_quarantine_instance_factory_v2_status"] == "PARTIAL_APPROVAL_FILE_ABSENT_NO_INSTANCES_CREATED"
    assert factory["created_quarantine_instance_count"] == 0
    assert not (tmp_path / "q").exists() or not list((tmp_path / "q").glob("*.json"))


def test_v57_malformed_approval_returns_partial_malformed(tmp_path) -> None:
    path = write_approval_file(tmp_path, "{ not json ]")
    reports = v57_reports(approval_path=path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "q")
    consumer = reports["v57_manual_approval_file_consumer_report.json"]
    factory = reports["v57_inert_quarantine_instance_factory_v2_report.json"]
    assert consumer["manual_approval_file_consumer_status"] == "PARTIAL_APPROVAL_FILE_MALFORMED"
    assert factory["inert_quarantine_instance_factory_v2_status"] == "PARTIAL_APPROVAL_FILE_MALFORMED_NO_INSTANCES_CREATED"
    assert factory["created_quarantine_instance_count"] == 0


def test_v57_fuzzy_or_live_approval_fails_closed(tmp_path) -> None:
    fuzzy_path = write_approval_file(tmp_path / "a", approval_input("I approve Dummy to create rehearsal artifacts"))
    consumer = v57_reports(approval_path=fuzzy_path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "qa")["v57_manual_approval_file_consumer_report.json"]
    assert consumer["manual_approval_file_consumer_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert consumer["approval_validated"] is False
    assert not (tmp_path / "qa").exists() or not list((tmp_path / "qa").glob("*.json"))

    live_path = write_approval_file(tmp_path / "b", approval_input(VALID_PHRASE + " and submit orders"))
    live = v57_reports(approval_path=live_path)["v57_manual_approval_file_consumer_report.json"]
    assert live["manual_approval_file_consumer_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert "LIVE_OR_BROAD_EXECUTION_LANGUAGE_REJECTED" in live["approval_result"]["blockers"]


def test_v57_exact_approval_creates_only_allowed_inert_instances(tmp_path) -> None:
    approval_dir = tmp_path / "approvals"
    quarantine_dir = tmp_path / "quarantine"
    path = write_approval_file(approval_dir, approval_input())
    reports = v57_reports(approval_path=path, write_quarantine_artifacts=True, quarantine_dir=quarantine_dir)
    consumer = reports["v57_manual_approval_file_consumer_report.json"]
    factory = reports["v57_inert_quarantine_instance_factory_v2_report.json"]
    final = reports["final_report_v57.json"]
    assert consumer["manual_approval_file_consumer_status"] == "PASS_MANUAL_APPROVAL_FILE_ACCEPTED"
    assert factory["inert_quarantine_instance_factory_v2_status"] == "PASS_INERT_QUARANTINE_INSTANCES_CREATED"
    assert factory["created_quarantine_instance_count"] == 4
    assert factory["created_artifact_types"] == [
        "REHEARSAL_PLAN_DRAFT",
        "REHEARSAL_RISK_CHECKLIST",
        "REHEARSAL_VALIDATION_CHECKLIST",
        "REHEARSAL_AUDIT_TEMPLATE",
    ]
    assert final["verdict"] == "PASS"
    assert final["current_next_action"] == "QUARANTINED_REHEARSAL_ARTIFACTS_CREATED_RELEASE_LOCKED"

    files = sorted(quarantine_dir.glob("*.json"))
    assert len(files) == 4
    forbidden_fields = {
        "order_id",
        "market_order",
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
    }
    for artifact_path in files:
        instance = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert instance["artifact_type"] in factory["created_artifact_types"]
        assert instance["approval_hash"] == consumer["approval_hash"]
        assert instance["inert_only"] is True
        assert instance["no_broker_payload"] is True
        assert instance["no_order_submission"] is True
        assert instance["no_live_trading"] is True
        assert instance["no_live_submit"] is True
        assert instance["no_caps_modification"] is True
        assert instance["quarantine_release_locked"] is True
        assert instance["execution_bridge_present"] is False
        assert forbidden_fields.isdisjoint(instance)

    # Dummy must never have created the real dedicated approval file.
    assert not DEFAULT_APPROVAL_INPUT_PATH.exists()


def test_v57_quarantine_release_lock_canary_readiness_and_execution_lock(tmp_path) -> None:
    path = write_approval_file(tmp_path, approval_input())

    release = assert_v57_report_named("v57_quarantine_release_lock_v2_report.json", "v57_quarantine_release_lock_v2_status", approval_path=path)
    assert release["v57_quarantine_release_lock_v2_status"] == "PASS_QUARANTINE_RELEASE_LOCKED_V2"
    assert release["release_path_present"] is False
    assert release["submit_path_present"] is False
    assert release["transform_to_broker_path_present"] is False
    assert release["dry_submit_conversion_present"] is False
    assert release["shadow_order_conversion_present"] is False

    canary = assert_v57_report_named("v57_canary_nonexecution_validator_v7_report.json", "canary_nonexecution_validator_v7_status", approval_path=path)
    assert canary["canary_nonexecution_validator_v7_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR_V7"
    assert canary["order_cancel_reference_detected"] is False
    assert canary["broker_payload_reference_detected"] is False
    assert canary["quarantine_release_path_reference_detected"] is False
    assert canary["capital_or_portfolio_reference_detected"] is False

    readiness = assert_v57_report_named("readiness_governor_v17_report.json", "readiness_governor_v17_status", approval_path=path)
    assert readiness["readiness_governor_v17_status"] == "PASS"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    assert readiness["current_next_action"] == "QUARANTINED_REHEARSAL_ARTIFACTS_CREATED_RELEASE_LOCKED"

    lock = assert_v57_report_named("execution_lock_deep_recheck_v16_report.json", "execution_lock_deep_recheck_v16_status", approval_path=path)
    assert lock["execution_lock_deep_recheck_v16_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["selected_action_can_trigger_execution"] is False


def test_v57_readiness_awaits_manual_file_by_default() -> None:
    readiness = assert_v57_report_named("readiness_governor_v17_report.json", "current_next_action")
    assert readiness["current_next_action"] == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True
