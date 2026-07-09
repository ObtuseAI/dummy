from __future__ import annotations

from predator_mesh.v63.reports import FORBIDDEN_SCHEMA_FIELDS, validate_schema
from scripts.generate_v63_reports import generate_all_v63_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def test_v63_schemas_are_inert_and_cannot_submit() -> None:
    reports = generate_all_v63_reports_for_tests()
    dry = reports["v63_dry_submit_schema_gate_report.json"]
    shadow = reports["v63_shadow_packet_schema_gate_report.json"]
    assert_staged_safe(dry)
    assert dry["v62_baseline_status"] == "PASS_V62_BASELINE_READBACK"
    assert dry["dry_submit_schema_gate_status"] == "PASS_DRY_SUBMIT_SCHEMA_INERT"
    assert shadow["shadow_packet_schema_gate_status"] == "PASS_SHADOW_PACKET_SCHEMA_INERT"
    assert dry["broker_submit_denial_proof_status"] == "PASS_BROKER_SUBMIT_DENIED"
    assert dry["schemas_can_submit"] is False
    assert dry["dry_submit_schema"]["broker_submit_enabled"] is False
    assert reports["final_report_v63.json"]["verdict"] == "PASS"


def test_v63_schema_validator_rejects_forbidden_fields() -> None:
    bad = {"schema_id": "x", "rehearsal_only": True, "broker_submit_enabled": True, "market_order": True, "submit_endpoint": "https://broker/submit"}
    result = validate_schema(bad)
    assert result["inert_pass"] is False
    assert "market_order" in result["forbidden_fields_present"]
    assert "submit_endpoint" in result["forbidden_fields_present"]
    assert set(FORBIDDEN_SCHEMA_FIELDS) >= {"market_order", "submit_endpoint"}


def test_v63_safety_and_locks() -> None:
    reports = generate_all_v63_reports_for_tests()
    for name, report in reports.items():
        if name == "final_report_v63.json":
            continue
        assert_staged_safe(report)
