from __future__ import annotations

from predator_mesh.v68.reports import FORBIDDEN_CANDIDATE_FIELDS, validate_candidate
from scripts.generate_v68_reports import generate_all_v68_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def test_v68_selects_inert_limit_only_candidate_no_submit() -> None:
    reports = generate_all_v68_reports_for_tests()
    selector = reports["v68_candidate_selector_report.json"]
    assert_staged_safe(selector)
    assert selector["v67_baseline_status"] == "PASS_V67_BASELINE_READBACK"
    assert selector["candidate_selector_status"] == "PASS_CANDIDATE_SELECTED_LIMIT_ONLY_NO_SUBMIT"
    cand = selector["candidate"]
    assert cand["limit_only"] is True
    assert cand["market_order_allowed"] is False
    assert cand["submit_enabled"] is False
    assert cand["broker_payload_created"] is False
    assert cand["live_trading"] is False
    assert not any(f in cand for f in FORBIDDEN_CANDIDATE_FIELDS)
    assert reports["final_report_v68.json"]["verdict"] == "PASS"


def test_v68_candidate_validator_rejects_forbidden_fields() -> None:
    bad = {"candidate_id": "x", "limit_only": True, "market_order_allowed": False, "submit_enabled": False, "broker_payload_created": False, "live_trading": False, "submit_endpoint": "https://broker/submit", "order_id": "R1"}
    result = validate_candidate(bad)
    assert result["inert_pass"] is False
    assert "submit_endpoint" in result["forbidden_fields_present"]
    assert "order_id" in result["forbidden_fields_present"]


def test_v68_safety_and_locks() -> None:
    for name, report in generate_all_v68_reports_for_tests().items():
        if name == "final_report_v68.json":
            continue
        assert_staged_safe(report)
