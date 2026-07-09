from __future__ import annotations

from predator_mesh.v34.run import ExactGateAcknowledgementHardeningV4
from tests.v34_test_helpers import assert_v34_report_named


def test_exact_gate_ack_v4_missing_values_fail_closed() -> None:
    decision = ExactGateAcknowledgementHardeningV4().validate({})

    assert decision.enabled is False
    assert decision.exact_ack_validation_status == "FAIL_MISSING_ACK"
    assert decision.failure_reason == "MISSING_MODE_AND_ACK"
    assert decision.probe_run_allowed is False
    assert decision.safe_metadata_only is True
    assert decision.execution_bridge_present is False


def test_exact_gate_ack_v4_fuzzy_trading_language_fails_closed() -> None:
    fuzzy = ExactGateAcknowledgementHardeningV4().validate({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY please submit live orders",
    })
    misspelled = ExactGateAcknowledgementHardeningV4().validate({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBE_ONLY",
    })

    assert fuzzy.enabled is False
    assert fuzzy.exact_ack_validation_status == "FAIL_TRADING_LANGUAGE"
    assert fuzzy.no_trading_language_guard_passed is False
    assert misspelled.enabled is False
    assert misspelled.exact_ack_validation_status == "FAIL_INVALID_ACK"


def test_exact_gate_ack_v4_report_contract() -> None:
    report = assert_v34_report_named("exact_gate_acknowledgement_hardening_v3_report.json", "exact_ack_validation_status")

    assert report["exact_ack_validation_status"] == "FAIL_MISSING_ACK"
    assert report["gate_state"] == "DISABLED_BY_DEFAULT"
    assert report["probe_run_allowed"] is False
