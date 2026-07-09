from __future__ import annotations

from pathlib import Path
from typing import Any

from predator_mesh.v55.reports import _approval_hash
from predator_mesh.v57.reports import _build_quarantine_instances, _write_quarantine_instances

VALID_APPROVAL_INPUT = {
    "exact_phrase": "I approve Dummy to create inert quarantined rehearsal artifacts only, with no broker submission, no live trading, no live-submit enablement, and no caps modification",
    "operator": "operator:chris",
    "timestamp": "2026-07-05T21:00:00Z",
    "reason": "create inert quarantined rehearsal planning artifacts only",
    "scope": "inert_quarantined_rehearsal_artifacts_only",
    "expiration": "2026-07-06T21:00:00Z",
    "non_live_trading_acknowledgment": "no live trading",
    "no_broker_submission_acknowledgment": "no broker submission",
    "no_live_submit_acknowledgment": "no live-submit enablement",
    "no_caps_modification_acknowledgment": "no caps modification",
}


def write_v57_inert_artifacts(quarantine_dir: Path) -> list[str]:
    """Create the exact 4 inert V57 quarantined artifacts in a temp directory (test fixture only)."""
    approval_hash = _approval_hash(VALID_APPROVAL_INPUT)
    instances = _build_quarantine_instances(VALID_APPROVAL_INPUT, approval_hash)
    return _write_quarantine_instances(instances, quarantine_dir)


def write_tampered_artifact(quarantine_dir: Path) -> Path:
    """Write an artifact carrying a forbidden field to prove the integrity validator rejects it."""
    import json

    quarantine_dir.mkdir(parents=True, exist_ok=True)
    approval_hash = _approval_hash(VALID_APPROVAL_INPUT)
    tampered = _build_quarantine_instances(VALID_APPROVAL_INPUT, approval_hash)[0]
    tampered["broker_payload"] = {"order_id": "X1", "side": "buy", "quantity": 1, "price": 100}
    path = quarantine_dir / "tampered.json"
    path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")
    return path


def v58_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from scripts.generate_v58_reports import generate_all_v58_reports_for_tests

    return generate_all_v58_reports_for_tests(**kwargs)


def assert_v58_safe(report: dict[str, Any]) -> None:
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["read_only_only"] is True
    assert report["execution_bridge_present"] is False
    assert report["approval_file_created"] is False
    assert report["approval_file_write_attempted"] is False
    assert report["default_quarantine_artifact_created"] is False
    assert report["quarantine_artifact_mutated"] is False
    assert report["reviewer_modified_artifacts"] is False
    assert report["order_endpoints_used"] is False
    assert report["cancel_endpoints_used"] is False
    assert report["order_tickets_created"] is False
    assert report["shadow_orders_created"] is False
    assert report["dry_submit_packets_created"] is False
    assert report["broker_payloads_created"] is False
    assert report["executable_rehearsal_created"] is False
    assert report["broker_schema_created"] is False
    assert report["order_intent_objects_created"] is False
    assert report["position_sizing_artifacts_created"] is False
    assert report["capital_allocation_artifacts_created"] is False
    assert report["portfolio_construction_artifacts_created"] is False
    assert report["account_balance_private_position_accessed"] is False
    assert report["browser_automation_added"] is False
    assert report["pageagent_added"] is False
    assert report["dom_extraction_added"] is False
    assert report["mined_repo_executed"] is False
    assert report["sports_source_activated"] is False
    assert report["live_trading_readiness_claim"] is False
    assert report["quarantine_release_locked"] is True
    assert report["quarantine_release_path_present"] is False
    assert report["transform_to_broker_path_present"] is False
    assert report["v58_execution_artifacts_created"] is False


def assert_v58_report_named(name: str, key: str | None = None, *, quarantine_dir: Path | None = None) -> dict[str, Any]:
    reports = v58_reports(quarantine_dir=quarantine_dir)
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert_v58_safe(report)
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report
