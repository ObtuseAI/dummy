from __future__ import annotations

from typing import Any


def v56_reports() -> dict[str, dict[str, Any]]:
    from scripts.generate_v56_reports import generate_all_v56_reports_for_tests

    return generate_all_v56_reports_for_tests()


def assert_v56_safe(report: dict[str, Any]) -> None:
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["read_only_only"] is True
    assert report["execution_bridge_present"] is False
    assert report["approval_file_created"] is False
    assert report["approval_file_write_attempted"] is False
    assert report["quarantine_artifact_instance_created"] is False
    assert report["quarantine_artifact_instance_write_attempted"] is False
    assert report["template_is_approval"] is False
    assert report["template_written_to_disk"] is False
    assert report["approval_inferred"] is False
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
    assert report["v56_execution_artifacts_created"] is False


def assert_v56_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v56_reports()
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert_v56_safe(report)
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report
