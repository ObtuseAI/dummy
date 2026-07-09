from __future__ import annotations

import json

from predator_mesh.v55.reports import DEFAULT_APPROVAL_INPUT_PATH
from predator_mesh.v58.reports import attempt_quarantine_release, review_quarantine_dir, validate_artifact_integrity
from tests.v58_test_helpers import (
    assert_v58_report_named,
    v58_reports,
    write_tampered_artifact,
    write_v57_inert_artifacts,
)


def test_v58_reads_v57_baseline_and_default_has_no_artifacts_to_review() -> None:
    report = assert_v58_report_named("v58_quarantine_artifact_reviewer_report.json", "quarantine_artifact_reviewer_status")
    assert report["v57_baseline_status"] == "PASS_V57_BASELINE_READBACK"
    assert report["v57_manual_approval_file_consumer_status"] == "PARTIAL_APPROVAL_FILE_ABSENT"
    assert report["v57_cumulative_real_scored_count"] == 222
    assert report["quarantine_artifact_reviewer_status"] == "PARTIAL_NO_QUARANTINE_ARTIFACTS_TO_REVIEW"
    assert report["reviewed_artifact_count"] == 0
    assert report["reviewer_modified_artifacts"] is False
    final = v58_reports()["final_report_v58.json"]
    assert final["verdict"] == "PARTIAL"
    assert "NO_QUARANTINE_ARTIFACTS_TO_REVIEW" in final["current_blockers"]
    assert final["current_next_action"] == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"


def test_v58_reviews_temp_inert_artifacts_and_passes_integrity(tmp_path) -> None:
    quarantine_dir = tmp_path / "quarantine"
    written = write_v57_inert_artifacts(quarantine_dir)
    assert len(written) == 4
    before = {p: (tmp_path / "quarantine" / p.name).read_bytes() for p in quarantine_dir.glob("*.json")}

    reports = v58_reports(quarantine_dir=quarantine_dir)
    reviewer = reports["v58_quarantine_artifact_reviewer_report.json"]
    integrity = reports["v58_artifact_integrity_validator_report.json"]
    final = reports["final_report_v58.json"]

    assert reviewer["quarantine_artifact_reviewer_status"] == "PASS_QUARANTINE_ARTIFACTS_REVIEWED"
    assert reviewer["reviewed_artifact_count"] == 4
    assert sorted(reviewer["reviewed_artifact_types"]) == [
        "REHEARSAL_AUDIT_TEMPLATE",
        "REHEARSAL_PLAN_DRAFT",
        "REHEARSAL_RISK_CHECKLIST",
        "REHEARSAL_VALIDATION_CHECKLIST",
    ]
    assert integrity["v58_artifact_integrity_validator_status"] == "PASS_ARTIFACT_INTEGRITY_VALIDATED"
    assert integrity["all_reviewed_artifacts_pass_integrity"] is True
    assert final["verdict"] == "PASS"
    assert final["current_next_action"] == "QUARANTINED_ARTIFACTS_REVIEWED_RELEASE_LOCKED"

    # Reviewer is read-only: on-disk bytes are unchanged.
    after = {p: p.read_bytes() for p in quarantine_dir.glob("*.json")}
    assert before == after


def test_v58_integrity_validator_rejects_forbidden_fields(tmp_path) -> None:
    quarantine_dir = tmp_path / "q"
    write_v57_inert_artifacts(quarantine_dir)
    write_tampered_artifact(quarantine_dir)
    reports = v58_reports(quarantine_dir=quarantine_dir)
    reviewer = reports["v58_quarantine_artifact_reviewer_report.json"]
    integrity = reports["v58_artifact_integrity_validator_report.json"]
    assert reviewer["quarantine_artifact_reviewer_status"] == "FAIL_ARTIFACT_INTEGRITY"
    assert integrity["v58_artifact_integrity_validator_status"] == "FAIL_ARTIFACT_INTEGRITY"
    tampered = next(entry for entry in integrity["cases"] if entry["path"].endswith("tampered.json"))
    assert tampered["integrity_pass"] is False
    assert "broker_payload" in tampered["forbidden_fields_present"]
    assert reports["final_report_v58.json"]["verdict"] == "FAIL"


def test_v58_release_denial_proof_fails_closed() -> None:
    report = assert_v58_report_named("v58_release_denial_proof_report.json", "v58_release_denial_proof_status")
    assert report["v58_release_denial_proof_status"] == "PASS_RELEASE_DENIED"
    result = attempt_quarantine_release()
    assert result["status"] == "FAIL_CLOSED_RELEASE_DENIED"
    assert result["released"] is False
    assert result["transformed"] is False
    assert result["submitted"] is False


def test_v58_canary_readiness_and_execution_lock(tmp_path) -> None:
    quarantine_dir = tmp_path / "q"
    write_v57_inert_artifacts(quarantine_dir)

    canary = v58_reports(quarantine_dir=quarantine_dir)["v58_canary_nonexecution_validator_v8_report.json"]
    assert canary["canary_nonexecution_validator_v8_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR_V8"
    assert canary["approval_file_write_reference_detected"] is False
    assert canary["quarantine_artifact_mutation_reference_detected"] is False
    assert canary["quarantine_release_path_reference_detected"] is False

    readiness = v58_reports(quarantine_dir=quarantine_dir)["readiness_governor_v18_report.json"]
    assert readiness["readiness_governor_v18_status"] == "PASS"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    assert readiness["current_next_action"] == "QUARANTINED_ARTIFACTS_REVIEWED_RELEASE_LOCKED"

    lock = v58_reports(quarantine_dir=quarantine_dir)["execution_lock_deep_recheck_v17_report.json"]
    assert lock["execution_lock_deep_recheck_v17_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["quarantine_artifact_mutated"] is False


def test_v58_default_readiness_awaits_manual_file() -> None:
    readiness = assert_v58_report_named("readiness_governor_v18_report.json", "current_next_action")
    assert readiness["current_next_action"] == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True


def test_v58_default_creates_no_approval_file_or_quarantine_artifacts() -> None:
    v58_reports()
    assert not DEFAULT_APPROVAL_INPUT_PATH.exists()


def test_v58_validate_artifact_integrity_pure_function(tmp_path) -> None:
    quarantine_dir = tmp_path / "q"
    write_v57_inert_artifacts(quarantine_dir)
    results = review_quarantine_dir(quarantine_dir)
    assert len(results) == 4
    assert all(validate_artifact_integrity(json.loads((quarantine_dir / f"{r['artifact_id']}.json").read_text()))["integrity_pass"] for r in results)
