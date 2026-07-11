from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from archive.routes.v49_routes import router
from predator_mesh.v49.reports import SAFETY_REPORT_NAMES
from tests.v49_test_helpers import RehearsalGateReviewReadOnlyTransport, assert_v49_report_named, v49_reports


def test_v49_exact_gate_default_and_fuzzy_ack_fail_closed() -> None:
    default = assert_v49_report_named("exact_gate_runtime_v17_report.json", "exact_gate_runtime_v17_status")
    assert default["exact_gate_runtime_v17_status"] == "PASS_BLOCKED"
    assert default["ack_decision"] == "FAIL_MISSING_ACK"
    assert default["probe_executed"] is False
    fuzzy = v49_reports(
        env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY submit broker"},
        enable_real_probe=True,
        real_transport=RehearsalGateReviewReadOnlyTransport(),
    )["exact_gate_runtime_v17_report.json"]
    assert fuzzy["ack_decision"] == "FAIL_FUZZY_ACK"
    assert fuzzy["v49_new_real_probe_count"] == 0
    assert fuzzy["trading_language_rejected"] is True


def test_v49_nonexecution_validator_and_safety_reports_are_read_only() -> None:
    validator = assert_v49_report_named("v49_nonexecution_validator_report.json", "nonexecution_validator_status", enabled=True)
    assert validator["nonexecution_validator_status"] == "PASS_NONEXECUTION_VALIDATOR"
    assert validator["orders_cancels_possible"] is False
    assert validator["broker_payloads_possible"] is False
    assert validator["execution_rehearsal_possible"] is False
    assert validator["capital_or_portfolio_possible"] is False
    assert validator["account_private_access_possible"] is False
    assert validator["live_submit_changes_possible"] is False
    assert validator["caps_changes_possible"] is False
    for name in SAFETY_REPORT_NAMES:
        report = assert_v49_report_named(name, "safety_status", enabled=True)
        assert report["safety_status"] == "PASS"
        assert report["v49_rehearsal_artifacts_created"] is False


def test_dashboard_v49_api_routes_are_read_only() -> None:
    report = assert_v49_report_named("dashboard_v49_report_v1.json", "dashboard_status")
    assert "/api/v49/rehearsal-gate-design-review-controller" in report["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v49/rehearsal-gate-design-review-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert "v49_rehearsal_gate_design_review_controller_report" in payload
