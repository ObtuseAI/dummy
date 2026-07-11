from __future__ import annotations

from typing import Any


class StableSampleReviewReadOnlyTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any] | list[dict[str, Any]]:
        self.calls.append(f"{task.lane_id}:{task.cycle}:{task.source_family}:{task.request_index}")
        if timeout_seconds > 12:
            raise AssertionError("V48 public observer timeout exceeded read-only budget")
        if task.source_family == "weather":
            return {"properties": {"temperature": {"value": 24.0 + task.cycle}, "timestamp": f"2026-07-05T3{task.cycle}:{task.request_index}0:00Z"}}
        if task.source_family == "crypto":
            return {"data": {"amount": str(68000 + task.cycle * 100 + task.request_index)}, "timestamp": f"2026-07-05T3{task.cycle}:{task.request_index}5:00Z"}
        if task.source_family == "public_event_reference":
            return [{"indicator": {"id": "SL.UEM.TOTL.ZS"}, "value": 4.0 + task.request_index, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


def v48_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v48_reports import generate_all_v48_reports_for_tests

    return generate_all_v48_reports_for_tests(**kwargs)


def v48_enabled_reports() -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v48_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=StableSampleReviewReadOnlyTransport())


def assert_v48_safe(report: dict[str, Any]) -> None:
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
    assert report["execution_rehearsal_created"] is False
    assert report["broker_schema_created"] is False
    assert report["order_intent_objects_created"] is False
    assert report["position_sizing_artifacts_created"] is False
    assert report["capital_allocation_artifacts_created"] is False
    assert report["portfolio_construction_artifacts_created"] is False
    assert report["account_balance_private_position_accessed"] is False
    assert report["browser_automation_added"] is False
    assert report["pageagent_added"] is False
    assert report["mined_repo_executed"] is False
    assert report["sports_source_activated"] is False
    assert report["live_trading_readiness_claim"] is False
    assert report["future_rehearsal_gate_design_only"] is True
    assert report["v48_rehearsal_artifacts_created"] is False


def assert_v48_report_named(name: str, key: str | None = None, *, enabled: bool = False) -> dict[str, Any]:
    reports = v48_enabled_reports() if enabled else v48_reports()
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert_v48_safe(report)
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report
