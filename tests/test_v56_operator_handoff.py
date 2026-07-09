from __future__ import annotations

from pathlib import Path

from predator_mesh.v56.reports import DEFAULT_APPROVAL_INPUT_PATH, LINTER_CASES, TEMPLATE_MARKER, lint_packet
from tests.v56_test_helpers import assert_v56_report_named, v56_reports


def test_v56_reads_v55_baseline_and_operator_handoff_ready() -> None:
    report = assert_v56_report_named("v56_operator_handoff_controller_report.json", "operator_handoff_status")
    assert report["v55_baseline_status"] == "PASS_V55_BASELINE_READBACK"
    assert report["v55_final_verdict"] == "PARTIAL"
    assert report["v55_created_quarantine_artifact_count"] == 0
    assert report["v55_cumulative_real_scored_count"] == 222
    assert report["operator_handoff_status"] == "PASS_OPERATOR_HANDOFF_READY"
    assert report["handoff_created_approval_file"] is False
    assert report["handoff_created_artifact_instance"] is False
    final = v56_reports()["final_report_v56.json"]
    assert final["verdict"] == "PASS"
    assert final["current_next_action"] == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"
    assert final["current_blockers"] == []


def test_v56_template_is_report_only_and_not_approval() -> None:
    report = assert_v56_report_named("v56_approval_packet_template_report.json", "template")
    assert report["v56_approval_packet_template_status"] == "PASS_TEMPLATE_REPORT_ONLY"
    assert report["marker"] == TEMPLATE_MARKER == "NOT_APPROVAL"
    assert report["is_approval"] is False
    assert report["written_to_disk"] is False
    for field in [
        "exact_phrase",
        "operator",
        "timestamp",
        "reason",
        "scope",
        "expiration",
        "non_live_trading_acknowledgment",
        "no_broker_submission_acknowledgment",
        "no_live_submit_acknowledgment",
        "no_caps_modification_acknowledgment",
    ]:
        assert field in report["template"]
    # The template must never have been materialized as a real approval file.
    assert not DEFAULT_APPROVAL_INPUT_PATH.exists()


def test_v56_linter_covers_all_packet_cases_in_memory() -> None:
    report = assert_v56_report_named("v56_approval_packet_linter_v1_report.json", "cases")
    assert report["v56_approval_packet_linter_v1_status"] == "PASS_APPROVAL_PACKET_LINTER"
    assert report["in_memory_only"] is True
    by_case = {entry["case"]: entry["status"] for entry in report["cases"]}
    assert by_case["absent_packet"] == "PARTIAL_APPROVAL_INPUT_ABSENT"
    assert by_case["malformed_packet"] == "PARTIAL_APPROVAL_INPUT_MALFORMED"
    assert by_case["fuzzy_phrase_packet"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert by_case["broad_live_trading_packet"] == "FAIL_CLOSED_INVALID_APPROVAL"
    assert by_case["exact_packet"] == "PASS_EXACT_PACKET_SHAPE_VALID"
    # Every case matches its expectation and the linter created no files.
    assert all(entry["matches"] for entry in report["cases"])
    assert report["approval_packet_linter_wrote_files"] is False


def test_v56_lint_packet_pure_function_matches_expectations() -> None:
    for _name, resolution, expected in LINTER_CASES:
        assert lint_packet(resolution) == expected


def test_v56_pre_artifact_lock_review_holds() -> None:
    report = assert_v56_report_named("v56_pre_artifact_lock_review_report.json", "v56_pre_artifact_lock_review_status")
    assert report["v56_pre_artifact_lock_review_status"] == "PASS_PRE_ARTIFACT_LOCK_HELD"
    assert report["artifact_factory_locked_by_default"] is True
    assert report["quarantine_instances_present_default"] is False
    assert report["artifact_release_path_present"] is False
    assert report["transform_to_broker_path_present"] is False


def test_v56_canary_readiness_and_execution_lock() -> None:
    canary = assert_v56_report_named("v56_canary_nonexecution_validator_v6_report.json", "canary_nonexecution_validator_v6_status")
    assert canary["canary_nonexecution_validator_v6_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR_V6"
    assert canary["approval_file_write_reference_detected"] is False
    assert canary["quarantine_artifact_instance_write_reference_detected"] is False
    assert canary["order_cancel_reference_detected"] is False
    assert canary["quarantine_release_path_reference_detected"] is False

    readiness = assert_v56_report_named("readiness_governor_v16_report.json", "readiness_governor_v16_status")
    assert readiness["readiness_governor_v16_status"] == "PASS"
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["QUARANTINE_RELEASE_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    assert readiness["current_next_action"] == "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"

    lock = assert_v56_report_named("execution_lock_deep_recheck_v15_report.json", "execution_lock_deep_recheck_v15_status")
    assert lock["execution_lock_deep_recheck_v15_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["selected_action_can_trigger_execution"] is False


def test_v56_does_not_create_approval_file_or_artifacts() -> None:
    quarantine_dir = Path("artifacts/dummy/v55_quarantine")
    v56_reports()
    assert not DEFAULT_APPROVAL_INPUT_PATH.exists()
    assert not (quarantine_dir.exists() and any(quarantine_dir.glob("*.json")))
