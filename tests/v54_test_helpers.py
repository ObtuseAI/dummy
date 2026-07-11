from __future__ import annotations

from pathlib import Path
from typing import Any


class ApprovalActuationReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.lane_id}:{task.cycle}:{task.source_family}:{task.request_index}")
        if timeout_seconds > 12:
            raise AssertionError("V54 public observer timeout exceeded read-only budget")
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
        "approval_phrase": phrase,
        "operator": "operator:chris",
        "timestamp": "2026-07-05T21:00:00Z",
        "reason": "create inert quarantined rehearsal planning artifacts only",
        "scope": "inert_quarantined_rehearsal_artifacts_only",
        "expiration": "2026-07-06T21:00:00Z",
        "non_live_trading_ack": "no live trading; no broker submission; no live-submit enablement; no caps modification",
    }


def v54_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v54_reports import generate_all_v54_reports_for_tests

    return generate_all_v54_reports_for_tests(**kwargs)


def v54_enabled_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v54_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=ApprovalActuationReadOnlyTransport(), **kwargs)


def assert_v54_safe(report: dict[str, Any]) -> None:
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
    assert report["v54_execution_artifacts_created"] is False


def assert_v54_report_named(
    name: str,
    key: str | None = None,
    *,
    enabled: bool = False,
    approval: dict[str, str] | None = None,
    write_quarantine_artifacts: bool = False,
    quarantine_dir: Path | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"approval_input": approval, "write_quarantine_artifacts": write_quarantine_artifacts, "quarantine_dir": quarantine_dir}
    reports = v54_enabled_reports(**kwargs) if enabled else v54_reports(**kwargs)
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert_v54_safe(report)
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report
