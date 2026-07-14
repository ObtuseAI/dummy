from __future__ import annotations

from tests.v52_test_helpers import assert_v52_report_named


VALID_PHRASE = "I approve Dummy to create inert quarantined rehearsal artifacts only, with no broker submission, no live trading, no live-submit enablement, and no caps modification"


def _packet(phrase: str = VALID_PHRASE) -> dict[str, str]:
    return {
        "approval_phrase": phrase,
        "operator_identity": "operator:chris",
        "timestamp": "2026-07-05T12:00:00Z",
        "reason": "review inert quarantined rehearsal artifact policy",
        "scope": "inert_quarantined_rehearsal_artifacts_only",
        "expiration": "2026-07-06T12:00:00Z",
        "max_artifact_type": "inert_json_only",
        "non_live_trading_ack": "no live trading; no broker submission; no live-submit enablement; no caps modification",
    }


def test_v52_v51_baseline_readback_preserves_approval_surface_authority() -> None:
    report = assert_v52_report_named("v51_baseline_readback_v1_report.json", "v51_baseline_status")
    assert report["v51_baseline_status"] == "PASS_V51_BASELINE_READBACK"
    assert report["v51_final_verdict"] == "PASS"
    assert report["v50_baseline_status"] == "PASS_V50_BASELINE_READBACK"
    assert report["v51_new_real_scored_count"] == 18
    assert report["v51_cumulative_real_scored_count"] == 180
    assert report["v51_approval_surface_status"] == "PASS_APPROVAL_SURFACE_LOCKED"
    assert report["v51_rehearsal_approval_policy_status"] == "PASS_REHEARSAL_APPROVAL_POLICY_LOCKED"
    assert report["v51_canary_nonexecution_validator_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR"
    assert report["v51_holdout_status"] == "PASS_HOLDOUT_CONTINUATION_READONLY"


def test_v52_approval_packet_validator_accepts_exact_packet_only() -> None:
    report = assert_v52_report_named("v52_approval_packet_validator_report.json", "approval_packet_validator_status", enabled=True)
    assert report["approval_packet_validator_status"] == "PASS_APPROVAL_PACKET_VALIDATOR_LOCKED"
    assert report["valid_packet_result"]["accepted"] is True
    assert report["valid_packet_result"]["creates_rehearsal_artifact"] is False
    assert report["fuzzy_phrase_result"]["accepted"] is False
    assert report["broad_phrase_result"]["accepted"] is False
    assert report["live_trading_phrase_result"]["accepted"] is False
    assert report["required_packet_fields"] == [
        "approval_phrase",
        "operator_identity",
        "timestamp",
        "reason",
        "scope",
        "expiration",
        "max_artifact_type",
        "non_live_trading_ack",
    ]


def test_v52_packet_validator_function_rejects_missing_fuzzy_broad_and_trading_packets() -> None:
    from predator_mesh.v52.reports import validate_approval_packet

    assert validate_approval_packet(_packet())["accepted"] is True
    assert validate_approval_packet(_packet("I approve Dummy to create rehearsal artifacts"))["accepted"] is False
    assert validate_approval_packet(_packet(VALID_PHRASE + " and trade live"))["accepted"] is False
    missing = _packet()
    missing.pop("expiration")
    assert validate_approval_packet(missing)["accepted"] is False


def test_v52_phrase_policy_and_quarantine_gate_are_policy_only() -> None:
    phrase = assert_v52_report_named("v52_approval_phrase_policy_report.json", "approval_phrase_policy_status", enabled=True)
    assert phrase["approval_phrase_policy_status"] == "PASS_APPROVAL_PHRASE_POLICY_LOCKED"
    assert phrase["exact_approval_phrase"] == VALID_PHRASE
    assert phrase["fuzzy_or_broader_phrase_fails_closed"] is True
    quarantine = assert_v52_report_named("v52_rehearsal_artifact_quarantine_gate_report.json", "quarantine_gate_status", enabled=True)
    assert quarantine["quarantine_gate_status"] == "PASS_REHEARSAL_ARTIFACT_QUARANTINE_GATE_POLICY_ONLY"
    assert quarantine["quarantine_artifacts_created"] is False
    assert quarantine["quarantine_release_requires_future_bundle"] is True
    assert quarantine["quarantine_artifacts_inert_json_only"] is True
    assert quarantine["quarantine_allows_broker_payloads"] is False
    assert quarantine["quarantine_allows_order_tickets"] is False


def test_v52_holdout_and_governors_stay_locked() -> None:
    holdout = assert_v52_report_named("v52_holdout_continuation_report.json", "holdout_continuation_status", enabled=True)
    assert holdout["holdout_continuation_status"] == "PASS_HOLDOUT_CONTINUATION_READONLY"
    assert holdout["v52_new_real_scored_count"] == 18
    assert holdout["cumulative_real_scored_count"] == 198
    assert holdout["max_total_requests"] == 24
    assert holdout["per_request_timeout_seconds"] == 12
    assert holdout["sports_excluded"] is True
    readiness = assert_v52_report_named("readiness_governor_v12_report.json", "readiness_governor_v12_status", enabled=True)
    assert readiness["readiness_governor_v12_status"] == "PASS"
    assert readiness["READONLY_APPROVAL_PACKET_VALIDATOR"] == "ACHIEVED"
    assert readiness["OPERATOR_ARMED_REHEARSAL_ARTIFACTS_LOCKED"] is True
    assert readiness["OPERATOR_ARMED_REHEARSAL_LOCKED"] is True
    assert readiness["LIVE_TRADING_LOCKED"] is True
    assert readiness["LIVE_SUBMIT_DISABLED"] is True
    assert readiness["CAPS_OPERATOR_CONTROLLED"] is True
    assert readiness["current_next_action"] == "AWAIT_EXPLICIT_REHEARSAL_ARTIFACT_APPROVAL"
    lock = assert_v52_report_named("execution_lock_deep_recheck_v11_report.json", "execution_lock_deep_recheck_v11_status", enabled=True)
    assert lock["execution_lock_deep_recheck_v11_status"] == "PASS"
    assert lock["workflow_to_execution_bridge_present"] is False
    assert lock["selected_action_can_trigger_execution"] is False
