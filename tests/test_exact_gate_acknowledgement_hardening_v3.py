from __future__ import annotations

from predator_mesh.v33.run import ExactGateAcknowledgementHardeningV3
from tests.v33_test_helpers import assert_v33_report_named


def test_exact_gate_ack_missing_values_fail_closed() -> None:
    decision = ExactGateAcknowledgementHardeningV3().validate({})

    assert decision.enabled is False
    assert decision.exact_ack_validation_status == "FAIL_MISSING_ACK"
    assert decision.failure_reason == "MISSING_MODE_AND_ACK"
    assert decision.operator_action == "set DUMMY_PUBLIC_PROBE_MODE=1 and DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY"
    assert decision.probe_run_allowed is False
    assert decision.safe_metadata_only is True
    assert decision.execution_bridge_present is False


def test_exact_gate_ack_fuzzy_or_live_trading_language_fails_closed() -> None:
    fuzzy = ExactGateAcknowledgementHardeningV3().validate({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY please submit live orders",
    })
    misspelled = ExactGateAcknowledgementHardeningV3().validate({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBE_ONLY",
    })

    assert fuzzy.enabled is False
    assert fuzzy.exact_ack_validation_status == "FAIL_TRADING_LANGUAGE"
    assert fuzzy.failure_reason == "TRADING_LANGUAGE_NOT_ALLOWED"
    assert fuzzy.no_trading_language_guard_passed is False
    assert misspelled.enabled is False
    assert misspelled.exact_ack_validation_status == "FAIL_INVALID_ACK"
    assert misspelled.failure_reason == "ACK_NOT_EXACT"


def test_exact_gate_ack_report_contract() -> None:
    report = assert_v33_report_named("exact_gate_acknowledgement_hardening_v3_report.json", "exact_ack_validation_status")

    assert report["exact_ack_validation_status"] == "FAIL_MISSING_ACK"
    assert report["gate_state"] == "DISABLED_BY_DEFAULT"
    assert report["probe_run_allowed"] is False
