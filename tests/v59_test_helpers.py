from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VALID_PHRASE = "I approve Dummy to create inert quarantined rehearsal artifacts only, with no broker submission, no live trading, no live-submit enablement, and no caps modification"


def approval_input(phrase: str = VALID_PHRASE) -> dict[str, str]:
    return {
        "exact_phrase": phrase,
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


def write_approval_file(directory: Path, data: Any) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "dummy_v55_rehearsal_artifact_approval.json"
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def v59_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v59_reports import generate_all_v59_reports_for_tests

    return generate_all_v59_reports_for_tests(**kwargs)


def assert_v59_safe(report: dict[str, Any]) -> None:
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["read_only_only"] is True
    assert report["execution_bridge_present"] is False
    assert report["approval_file_created"] is False
    assert report["approval_file_modified"] is False
    assert report["approval_file_auto_filled"] is False
    assert report["approval_file_write_attempted"] is False
    assert report["default_quarantine_artifact_created"] is False
    assert report["unauthorized_artifact_mutation"] is False
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
    assert report["v59_execution_artifacts_created"] is False


def assert_v59_report_named(
    name: str,
    key: str | None = None,
    *,
    approval: dict[str, str] | None = None,
    approval_path: Path | None = None,
    write_quarantine_artifacts: bool = False,
    quarantine_dir: Path | None = None,
) -> dict[str, Any]:
    reports = v59_reports(
        approval_input=approval,
        approval_path=approval_path,
        write_quarantine_artifacts=write_quarantine_artifacts,
        quarantine_dir=quarantine_dir,
    )
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert_v59_safe(report)
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report
