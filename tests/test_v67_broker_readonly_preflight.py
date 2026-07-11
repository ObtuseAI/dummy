from __future__ import annotations

from predator_mesh.v67.reports import BROKER_READONLY_PHRASE
from archive.report_scripts.generate_v67_reports import generate_all_v67_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def test_v67_readonly_preflight_private_access_locked_by_default() -> None:
    reports = generate_all_v67_reports_for_tests()
    controller = reports["v67_broker_readonly_preflight_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["v66_baseline_status"] == "PASS_V66_BASELINE_READBACK"
    assert controller["broker_readonly_preflight_controller_status"] == "PASS_BROKER_READONLY_PREFLIGHT_PRIVATE_ACCESS_LOCKED"
    assert controller["secret_redaction_scanner_status"] == "PASS_SECRETS_REDACTED"
    assert controller["private_data_access_denial_proof_status"] == "PASS_PRIVATE_ACCESS_DENIED"
    assert controller["broker_readonly_approval_validator_status"] == "PARTIAL_BROKER_READONLY_APPROVAL_ABSENT"
    assert controller["account_read"] is False and controller["balance_read"] is False and controller["position_read"] is False
    assert controller["safe_connection_shape"]["api_key_present"] is False
    assert reports["final_report_v67.json"]["verdict"] == "PASS"


def test_v67_no_secrets_in_connection_shape() -> None:
    import json

    shape = generate_all_v67_reports_for_tests()["v67_safe_connection_shape_report.json"]["safe_connection_shape"]
    assert shape["auth_value_redacted"] is True
    assert "secret" not in json.dumps(shape).lower() or shape["credential_value"] == "<redacted>"


def test_v67_broker_readonly_approval_is_separate_phrase() -> None:
    controller = generate_all_v67_reports_for_tests(broker_readonly_approval={"exact_phrase": BROKER_READONLY_PHRASE})["v67_broker_readonly_preflight_controller_report.json"]
    assert controller["broker_readonly_approval_validator_status"] == "PASS_BROKER_READONLY_APPROVAL_PRESENT"
    # Even with read-only approval, no order/submit surfaces appear.
    assert_staged_safe(controller)


def test_v67_safety_and_locks() -> None:
    for name, report in generate_all_v67_reports_for_tests().items():
        if name == "final_report_v67.json":
            continue
        assert_staged_safe(report)
