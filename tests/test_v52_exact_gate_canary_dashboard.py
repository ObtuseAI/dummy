from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.backend.v52_routes import router
from predator_mesh.v52.reports import SAFETY_REPORT_NAMES
from tests.v52_test_helpers import ApprovalPacketReadOnlyTransport, assert_v52_report_named, v52_reports


def test_v52_exact_gate_default_and_fuzzy_ack_fail_closed() -> None:
    default = assert_v52_report_named("exact_gate_runtime_v20_report.json", "exact_gate_runtime_v20_status")
    assert default["exact_gate_runtime_v20_status"] == "PASS_BLOCKED"
    assert default["ack_decision"] == "FAIL_MISSING_ACK"
    assert default["probe_executed"] is False
    fuzzy = v52_reports(
        env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY submit broker"},
        enable_real_probe=True,
        real_transport=ApprovalPacketReadOnlyTransport(),
    )["exact_gate_runtime_v20_report.json"]
    assert fuzzy["ack_decision"] == "FAIL_FUZZY_ACK"
    assert fuzzy["v52_new_real_probe_count"] == 0
    assert fuzzy["trading_language_rejected"] is True


def test_v52_canary_nonexecution_validator_v2_and_safety_reports_are_read_only() -> None:
    validator = assert_v52_report_named("v52_canary_nonexecution_validator_v2_report.json", "canary_nonexecution_validator_v2_status", enabled=True)
    assert validator["canary_nonexecution_validator_v2_status"] == "PASS_CANARY_NONEXECUTION_VALIDATOR_V2"
    assert validator["order_cancel_reference_detected"] is False
    assert validator["order_ticket_reference_detected"] is False
    assert validator["shadow_order_reference_detected"] is False
    assert validator["dry_submit_packet_reference_detected"] is False
    assert validator["broker_payload_reference_detected"] is False
    assert validator["execution_rehearsal_reference_detected"] is False
    assert validator["broker_schema_reference_detected"] is False
    assert validator["order_intent_reference_detected"] is False
    assert validator["capital_or_portfolio_reference_detected"] is False
    assert validator["account_private_access_reference_detected"] is False
    assert validator["live_submit_caps_mutation_reference_detected"] is False
    assert validator["quarantine_artifact_creation_detected"] is False
    for name in SAFETY_REPORT_NAMES:
        report = assert_v52_report_named(name, "safety_status", enabled=True)
        assert report["safety_status"] == "PASS"
        assert report["v52_execution_artifacts_created"] is False
        assert report["quarantine_artifacts_created"] is False


def test_dashboard_v52_api_routes_are_read_only() -> None:
    report = assert_v52_report_named("dashboard_v52_report_v1.json", "dashboard_status")
    assert "/api/v52/approval-packet-validator" in report["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v52/approval-packet-validator")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert "v52_approval_packet_validator_report" in payload
