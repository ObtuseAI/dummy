from __future__ import annotations

from typing import Any


class ApprovalIntakeReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.lane_id}:{task.cycle}:{task.source_family}:{task.request_index}")
        if timeout_seconds > 12:
            raise AssertionError("V53 public observer timeout exceeded read-only budget")
        if task.source_family == "weather":
            return {"properties": {"temperature": {"value": 18.0 + task.cycle}, "timestamp": f"2026-07-05T8{task.cycle}:{task.request_index}0:00Z"}}
        if task.source_family == "crypto":
            return {"data": {"amount": str(74000 + task.cycle * 100 + task.request_index)}, "timestamp": f"2026-07-05T8{task.cycle}:{task.request_index}5:00Z"}
        if task.source_family == "public_event_reference":
            return [{"indicator": {"id": "FP.CPI.TOTL.ZG"}, "value": 3.0 + task.request_index, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


VALID_PHRASE = "I approve Dummy to create inert quarantined rehearsal artifacts only, with no broker submission, no live trading, no live-submit enablement, and no caps modification"


def approval_input(phrase: str = VALID_PHRASE) -> dict[str, str]:
    return {
        "approval_phrase": phrase,
        "operator_identity": "operator:chris",
        "timestamp": "2026-07-05T13:00:00Z",
        "reason": "authorize future inert quarantine manifest policy intake only",
        "scope": "inert_quarantined_rehearsal_artifacts_only",
        "expiration": "2026-07-06T13:00:00Z",
        "non_live_trading_ack": "no live trading; no broker submission; no live-submit enablement; no caps modification",
    }


def v53_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v53_reports import generate_all_v53_reports_for_tests

    return generate_all_v53_reports_for_tests(**kwargs)


def v53_enabled_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v53_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=ApprovalIntakeReadOnlyTransport(), **kwargs)


def assert_v53_safe(report: dict[str, Any]) -> None:
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
    assert report["quarantine_artifact_instances_created"] is False
    assert report["quarantine_manifest_instances_created"] is False
    assert report["browser_automation_added"] is False
    assert report["pageagent_added"] is False
    assert report["dom_extraction_added"] is False
    assert report["mined_repo_executed"] is False
    assert report["sports_source_activated"] is False
    assert report["live_trading_readiness_claim"] is False
    assert report["approval_intake_policy_only"] is True
    assert report["quarantine_manifest_dry_policy_only"] is True
    assert report["v53_execution_artifacts_created"] is False


def assert_v53_report_named(name: str, key: str | None = None, *, enabled: bool = False, approval: dict[str, str] | None = None) -> dict[str, Any]:
    reports = v53_enabled_reports(approval_input=approval) if enabled else v53_reports(approval_input=approval)
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert_v53_safe(report)
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report
