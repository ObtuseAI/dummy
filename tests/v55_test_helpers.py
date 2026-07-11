from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ApprovalWiringReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.lane_id}:{task.cycle}:{task.source_family}:{task.request_index}")
        if timeout_seconds > 12:
            raise AssertionError("V55 public observer timeout exceeded read-only budget")
        if task.source_family == "weather":
            return {"properties": {"temperature": {"value": 20.0 + task.cycle}, "timestamp": f"2026-07-05T9{task.cycle}:{task.request_index}0:00Z"}}
        if task.source_family == "crypto":
            return {"data": {"amount": str(75000 + task.cycle * 100 + task.request_index)}, "timestamp": f"2026-07-05T9{task.cycle}:{task.request_index}5:00Z"}
        if task.source_family == "public_event_reference":
            return [{"indicator": {"id": "SL.UEM.TOTL.ZS"}, "value": 4.0 + task.request_index, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


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


def v55_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v55_reports import generate_all_v55_reports_for_tests

    return generate_all_v55_reports_for_tests(**kwargs)


def v55_enabled_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v55_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=ApprovalWiringReadOnlyTransport(), **kwargs)


def assert_v55_safe(report: dict[str, Any]) -> None:
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["read_only_only"] is True
    assert report["execution_bridge_present"] is False
    assert report["order_endpoints_used"] is False
    assert report["cancel_endpoints_used"] is False
    assert report["order_tickets_created"] is False
    assert report["shadow_orders_created"] is False
    assert report["dry_submit_packets_created"] is False
    assert report["broker_payloads_created"] is False
    assert report["executable_rehearsal_created"] is False
    assert report["execution_rehearsal_created"] is False
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
    assert report["v55_execution_artifacts_created"] is False


def assert_v55_report_named(
    name: str,
    key: str | None = None,
    *,
    enabled: bool = False,
    approval: dict[str, str] | None = None,
    approval_path: Path | None = None,
    write_quarantine_artifacts: bool = False,
    quarantine_dir: Path | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "approval_input": approval,
        "approval_path": approval_path,
        "write_quarantine_artifacts": write_quarantine_artifacts,
        "quarantine_dir": quarantine_dir,
    }
    reports = v55_enabled_reports(**kwargs) if enabled else v55_reports(**kwargs)
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert_v55_safe(report)
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report
