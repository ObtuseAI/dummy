from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.backend.v48_routes import router
from predator_mesh.v48.reports import SAFETY_REPORT_NAMES
from tests.v48_test_helpers import StableSampleReviewReadOnlyTransport, assert_v48_report_named, v48_reports


def test_v48_exact_gate_default_and_fuzzy_ack_fail_closed() -> None:
    default = assert_v48_report_named("exact_gate_runtime_v16_report.json", "exact_gate_runtime_v16_status")
    assert default["exact_gate_runtime_v16_status"] == "PASS_BLOCKED"
    assert default["ack_decision"] == "FAIL_MISSING_ACK"
    fuzzy = v48_reports(
        env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY broker"},
        enable_real_probe=True,
        real_transport=StableSampleReviewReadOnlyTransport(),
    )["exact_gate_runtime_v16_report.json"]
    assert fuzzy["ack_decision"] == "FAIL_FUZZY_ACK"
    assert fuzzy["v48_new_real_probe_count"] == 0
    assert fuzzy["trading_language_rejected"] is True


def test_v48_safety_reports_and_runtime_budget_are_read_only() -> None:
    budget = assert_v48_report_named("v48_runtime_budget_report.json", "v48_runtime_budget_status", enabled=True)
    assert budget["max_total_requests"] == 24
    assert budget["per_request_timeout_seconds"] == 12
    assert budget["normal_tests_live_network"] is False
    for name in SAFETY_REPORT_NAMES:
        report = assert_v48_report_named(name, "safety_status", enabled=True)
        assert report["safety_status"] == "PASS"
        assert report["v48_rehearsal_artifacts_created"] is False


def test_dashboard_v48_api_routes_are_read_only() -> None:
    report = assert_v48_report_named("dashboard_v48_report_v1.json", "dashboard_status")
    assert "/api/v48/stable-sample-review-controller" in report["routes"]
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/v48/stable-sample-review-controller")
    assert response.status_code == 200
    payload = response.json()
    assert payload["api_can_trigger_probes"] is False
    assert payload["api_can_trigger_trading"] is False
    assert "v48_stable_sample_review_controller_report" in payload
