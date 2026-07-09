from __future__ import annotations

from tests.v53_test_helpers import VALID_PHRASE, approval_input, assert_v53_report_named, v53_enabled_reports


def test_v53_v52_baseline_readback_preserves_approval_packet_authority() -> None:
    report = assert_v53_report_named("v52_baseline_readback_v1_report.json", "v52_baseline_status")
    assert report["v52_baseline_status"] == "PASS_V52_BASELINE_READBACK"
    assert report["v52_final_verdict"] == "PASS"
    assert report["v51_baseline_status"] == "PASS_V51_BASELINE_READBACK"
    assert report["v52_new_real_probe_count"] == 18
    assert report["v52_new_evidence_count"] == 18
    assert report["v52_new_real_scored_count"] == 18
    assert report["v52_cumulative_real_scored_count"] == 198
    assert report["v52_approval_packet_validator_status"] == "PASS_APPROVAL_PACKET_VALIDATOR_LOCKED"
    assert report["v52_phrase_policy_status"] == "PASS_APPROVAL_PHRASE_POLICY_LOCKED"
    assert report["v52_quarantine_gate_status"] == "PASS_REHEARSAL_ARTIFACT_QUARANTINE_GATE_POLICY_ONLY"
    assert report["v52_canary_v2_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR_V2"


def test_v53_approval_intake_defaults_to_partial_when_dedicated_input_absent() -> None:
    report = assert_v53_report_named("v53_approval_intake_controller_report.json", "approval_intake_status")
    assert report["approval_intake_status"] == "PARTIAL_APPROVAL_NOT_PROVIDED"
    assert report["prompt_text_treated_as_approval"] is False
    assert report["dedicated_v53_approval_input_present"] is False
    assert report["approval_validated"] is False
    assert report["quarantine_manifest_instances_created"] is False
    assert report["quarantine_artifact_instances_created"] is False
    final = v53_enabled_reports()["final_report_v53.json"]
    assert final["verdict"] == "PARTIAL"
    assert "APPROVAL_INPUT_ABSENT" in final["current_blockers"]
    assert final["current_next_action"] == "AWAIT_EXPLICIT_REHEARSAL_ARTIFACT_APPROVAL"


def test_v53_approval_intake_accepts_exact_dedicated_input_for_future_quarantine_only() -> None:
    report = assert_v53_report_named("v53_approval_intake_controller_report.json", "approval_intake_status", enabled=True, approval=approval_input())
    assert report["approval_intake_status"] == "PASS_EXACT_APPROVAL_VALIDATED_FOR_FUTURE_QUARANTINE_ONLY"
    assert report["dedicated_v53_approval_input_present"] is True
    assert report["approval_validated"] is True
    assert report["approval_result"]["accepted"] is True
    assert report["approval_result"]["creates_rehearsal_artifact"] is False
    assert report["approval_result"]["creates_quarantine_artifact"] is False
    final = v53_enabled_reports(approval_input=approval_input())["final_report_v53.json"]
    assert final["verdict"] == "PASS"
    assert final["current_next_action"] == "APPROVAL_VALIDATED_FOR_FUTURE_QUARANTINE_ONLY"
    assert final["v53_new_real_scored_count"] == 12
    assert final["cumulative_real_scored_count"] == 210


def test_v53_approval_intake_rejects_fuzzy_broad_and_live_trading_wording() -> None:
    from predator_mesh.v53.reports import validate_v53_approval_input

    assert validate_v53_approval_input(approval_input())["accepted"] is True
    assert validate_v53_approval_input(approval_input("I approve Dummy to create rehearsal artifacts"))["accepted"] is False
    assert validate_v53_approval_input(approval_input(VALID_PHRASE + " and trade live"))["accepted"] is False
    missing = approval_input()
    missing.pop("expiration")
    assert validate_v53_approval_input(missing)["accepted"] is False
