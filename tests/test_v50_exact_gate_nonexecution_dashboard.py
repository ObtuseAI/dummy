from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from archive.routes.v50_routes import router
from predator_mesh.v50.reports import SAFETY_REPORT_NAMES
from tests.v50_test_helpers import LockedPreflightReadOnlyTransport, assert_v50_report_named, v50_reports


def test_v50_exact_gate_default_and_fuzzy_ack_fail_closed() -> None:
    default = assert_v50_report_named("exact_gate_runtime_v18_report.json", "exact_gate_runtime_v18_status")
    assert default["exact_gate_runtime_v18_status"] == "PASS_BLOCKED"
    assert default["ack_decision"] == "FAIL_MISSING_ACK"
    assert default["probe_executed"] is False
    fuzzy = v50_reports(
        env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY order cancel"},
        enable_real_probe=True,
        real_transport=LockedPreflightReadOnlyTransport(),
    )["exact_gate_runtime_v18_report.json"]
    assert fuzzy["ack_decision"] == "FAIL_FUZZY_ACK"
    assert fuzzy["v50_new_real_probe_count"] == 0
    assert fuzzy["trading_language_rejected"] is True


def test_v50_nonexecution_validator_v2_and_safety_reports_are_read_only() -> None:
    validator = assert_v50_report_named("v50_nonexecution_validator_v2_report.json", "nonexecution_validator_v2_status", enabled=True)
    assert validator["nonexecution_validator_v2_status"] == "PASS_NONEXECUTION_VALIDATOR_V2"
    assert validator["order_cancel_calls_possible"] is False
    assert validator["order_tickets_possible"] is False
    assert validator["shadow_orders_possible"] is False
    assert validator["dry_submit_packets_possible"] is False
    assert validator["broker_payloads_possible"] is False
    assert validator["executable_rehearsal_possible"] is False
    assert validator["capital_or_portfolio_possible"] is False
    assert validator["account_private_access_possible"] is False
    assert validator["live_submit_or_caps_changes_possible"] is False
    for name in SAFETY_REPORT_NAMES:
        report = assert_v50_report_named(name, "safety_status", enabled=True)
        assert report["safety_status"] == "PASS"
        assert report["v50_execution_artifacts_created"] is False


def test_dashboard_v50_api_routes_are_read_only() -> None:
    report = assert_v50_report_named("dashboard_v50_report_v1.json", "dashboard_status")
    assert "/api/v50/locked-rehearsal-preflight-controller" in report["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v50/locked-rehearsal-preflight-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert "v50_locked_rehearsal_preflight_controller_report" in payload
