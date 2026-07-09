from __future__ import annotations

import json

from tests.v55_test_helpers import (
    VALID_PHRASE,
    approval_input,
    assert_v55_report_named,
    v55_enabled_reports,
    v55_reports,
    write_approval_file,
)


def test_v55_reads_v54_baseline_and_defaults_to_partial_without_dedicated_approval() -> None:
    report = assert_v55_report_named("v55_dedicated_approval_input_resolver_report.json", "approval_resolver_status")
    assert report["v54_baseline_status"] == "PASS_V54_BASELINE_READBACK"
    assert report["v54_final_verdict"] == "PARTIAL"
    assert report["v54_new_real_scored_count"] == 12
    assert report["v54_cumulative_real_scored_count"] == 222
    assert report["approval_resolver_status"] == "PARTIAL_APPROVAL_INPUT_ABSENT"
    assert report["prompt_text_treated_as_approval"] is False
    assert report["env_var_treated_as_approval"] is False
    assert report["tests_treated_as_approval"] is False
    assert report["previous_artifacts_treated_as_approval"] is False
    assert report["dedicated_v55_approval_input_present"] is False
    assert report["approval_validated"] is False
    assert report["created_quarantine_artifact_count"] == 0
    final = v55_reports()["final_report_v55.json"]
    assert final["verdict"] == "PARTIAL"
    assert "APPROVAL_INPUT_ABSENT" in final["current_blockers"]
    assert final["current_next_action"] == "AWAIT_EXPLICIT_REHEARSAL_ARTIFACT_APPROVAL"


def test_v55_absent_approval_file_fails_closed_with_zero_artifacts(tmp_path) -> None:
    missing_path = tmp_path / "does_not_exist.json"
    reports = v55_reports(approval_path=missing_path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "q")
    resolver = reports["v55_dedicated_approval_input_resolver_report.json"]
    guard = reports["v55_quarantine_artifact_instance_guard_report.json"]
    assert resolver["approval_resolver_status"] == "PARTIAL_APPROVAL_INPUT_ABSENT"
    assert resolver["approval_input_resolution"] == "ABSENT"
    assert guard["created_quarantine_artifact_count"] == 0
    assert not list((tmp_path / "q").glob("*.json")) if (tmp_path / "q").exists() else True


def test_v55_malformed_approval_file_returns_partial_malformed(tmp_path) -> None:
    path = write_approval_file(tmp_path, "{ this is : not json ]")
    reports = v55_reports(approval_path=path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "q")
    resolver = reports["v55_dedicated_approval_input_resolver_report.json"]
    guard = reports["v55_quarantine_artifact_instance_guard_report.json"]
    assert resolver["approval_resolver_status"] == "PARTIAL_APPROVAL_INPUT_MALFORMED"
    assert resolver["approval_input_resolution"] == "MALFORMED"
    assert "APPROVAL_INPUT_MALFORMED" in resolver["approval_result"]["blockers"]
    assert guard["artifact_instance_guard_status"] == "PARTIAL_APPROVAL_INPUT_MALFORMED_NO_ARTIFACTS_CREATED"
    assert guard["created_quarantine_artifact_count"] == 0


def test_v55_exact_approval_file_creates_only_allowed_inert_quarantine_artifacts(tmp_path) -> None:
    approval_dir = tmp_path / "approvals"
    quarantine_dir = tmp_path / "quarantine"
    path = write_approval_file(approval_dir, approval_input())
    reports = v55_enabled_reports(approval_path=path, write_quarantine_artifacts=True, quarantine_dir=quarantine_dir)
    resolver = reports["v55_dedicated_approval_input_resolver_report.json"]
    guard = reports["v55_quarantine_artifact_instance_guard_report.json"]
    schema = reports["v55_inert_quarantine_artifact_schema_v2_report.json"]
    final = reports["final_report_v55.json"]
    assert resolver["approval_resolver_status"] == "PASS_EXACT_APPROVAL_ACCEPTED_FOR_INERT_QUARANTINE_ONLY"
    assert guard["artifact_instance_guard_status"] == "PASS_INERT_QUARANTINE_ARTIFACTS_CREATED"
    assert guard["created_quarantine_artifact_count"] == 4
    assert guard["created_artifact_types"] == [
        "REHEARSAL_PLAN_DRAFT",
        "REHEARSAL_RISK_CHECKLIST",
        "REHEARSAL_VALIDATION_CHECKLIST",
        "REHEARSAL_AUDIT_TEMPLATE",
    ]
    assert schema["schema_version"] == 2
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
        "order",
        "market_id",
        "account",
        "balance",
        "position",
        "size",
        "command",
    }
    for artifact_path in files:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert artifact["artifact_type"] in guard["created_artifact_types"]
        assert artifact["approval_hash"] == resolver["approval_hash"]
        assert artifact["operator"] == "operator:chris"
        assert artifact["inert_only"] is True
        assert artifact["no_broker_payload"] is True
        assert artifact["no_order_submission"] is True
        assert artifact["no_live_trading"] is True
        assert artifact["no_live_submit"] is True
        assert artifact["no_caps_modification"] is True
        assert artifact["quarantine_release_locked"] is True
        assert artifact["execution_bridge_present"] is False
        assert forbidden_fields.isdisjoint(artifact)


def test_v55_fuzzy_broad_or_live_approval_fails_closed_and_creates_no_artifacts(tmp_path) -> None:
    fuzzy_path = write_approval_file(tmp_path / "a", approval_input("I approve Dummy to create rehearsal artifacts"))
    reports = v55_reports(approval_path=fuzzy_path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "q")
    resolver = reports["v55_dedicated_approval_input_resolver_report.json"]
    guard = reports["v55_quarantine_artifact_instance_guard_report.json"]
    assert resolver["approval_resolver_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert resolver["approval_validated"] is False
    assert "APPROVAL_PHRASE_NOT_EXACT" in resolver["approval_result"]["blockers"]
    assert guard["artifact_instance_guard_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert guard["created_quarantine_artifact_count"] == 0
    assert not list((tmp_path / "q").glob("*.json")) if (tmp_path / "q").exists() else True

    live_path = write_approval_file(tmp_path / "b", approval_input(VALID_PHRASE + " and submit orders"))
    live = v55_reports(approval_path=live_path)["v55_dedicated_approval_input_resolver_report.json"]
    assert live["approval_resolver_status"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert "LIVE_OR_BROAD_EXECUTION_LANGUAGE_REJECTED" in live["approval_result"]["blockers"]


def test_v55_approval_audit_ledger_records_safe_metadata_only(tmp_path) -> None:
    path = write_approval_file(tmp_path, approval_input())
    ledger = v55_enabled_reports(approval_path=path, write_quarantine_artifacts=True, quarantine_dir=tmp_path / "q")[
        "v55_approval_input_audit_ledger_report.json"
    ]
    assert ledger["v55_approval_input_audit_ledger_status"] == "PASS"
    assert ledger["approval_inputs_recorded"] == 1
    assert ledger["artifact_records_recorded"] == 4
    assert ledger["approval_hash_recorded"]
    assert ledger["raw_approval_values_recorded"] is False
    assert ledger["approval_secrets_recorded"] is False
    assert ledger["environment_dumped"] is False
    assert ledger["account_or_private_data_recorded"] is False
    # The ledger records the hash and decision only; it never carries the operator's raw
    # submitted approval input (no raw-phrase / raw-acknowledgment / raw-input field).
    assert "exact_phrase" not in ledger
    assert "raw_approval_input" not in ledger
    assert "non_live_trading_acknowledgment" not in ledger
    assert isinstance(ledger["approval_hash_recorded"], str) and len(ledger["approval_hash_recorded"]) == 64


def test_v55_quarantine_release_lock_canary_readiness_and_execution_lock(tmp_path) -> None:
    path = write_approval_file(tmp_path, approval_input())

    canary = assert_v55_report_named("v55_canary_nonexecution_validator_v5_report.json", "canary_nonexecution_validator_v5_status", enabled=True, approval_path=path)
    assert canary["canary_nonexecution_validator_v5_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR_V5"
    assert canary["order_cancel_reference_detected"] is False
    assert canary["broker_payload_reference_detected"] is False
    assert canary["quarantine_release_path_reference_detected"] is False
    assert canary["capital_or_portfolio_reference_detected"] is False
    assert canary["account_private_access_reference_detected"] is False
    assert canary["quarantine_release_lock_status"] == "PASS_QUARANTINE_RELEASE_LOCKED"
    assert canary["quarantine_to_execution_transform_status"] == "FAIL_CLOSED_NO_TRANSFORM_PATH"

    readiness = assert_v55_report_named("readiness_governor_v15_report.json", "readiness_governor_v15_status", enabled=True, approval_path=path)
    assert readiness["readiness_governor_v15_status"] == "PASS"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    assert readiness["current_next_action"] == "QUARANTINED_REHEARSAL_ARTIFACTS_CREATED_RELEASE_LOCKED"

    lock = assert_v55_report_named("execution_lock_deep_recheck_v14_report.json", "execution_lock_deep_recheck_v14_status", enabled=True, approval_path=path)
    assert lock["execution_lock_deep_recheck_v14_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["selected_action_can_trigger_execution"] is False


def test_v55_readiness_governor_awaits_approval_by_default() -> None:
    readiness = assert_v55_report_named("readiness_governor_v15_report.json", "current_next_action")
    assert readiness["current_next_action"] == "AWAIT_EXPLICIT_REHEARSAL_ARTIFACT_APPROVAL"
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True
