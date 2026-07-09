from __future__ import annotations

from typing import Any

# Safety keys every staged-gate (V60-V65) report must assert fail-closed.
STAGED_SAFE_FALSE_KEYS = [
    "execution_bridge_present",
    "approval_file_created",
    "approval_file_modified",
    "live_trading_enabled",
    "live_order_submitted",
    "market_order_created",
    "market_order_allowed",
    "live_submit_enabled",
    "caps_modified",
    "account_balance_private_position_accessed",
    "private_account_accessed",
    "broker_submit_call_made",
    "broker_cancel_call_made",
    "submit_call_present",
    "cancel_call_present",
    "broker_payload_with_submit_authority",
    "broker_payloads_created",
    "executable_order_path_present",
    "order_tickets_created",
    "shadow_orders_created",
    "dry_submit_packets_created",
    "order_intent_objects_created",
    "position_sizing_artifacts_created",
    "capital_allocation_artifacts_created",
    "portfolio_construction_artifacts_created",
    "executable_rehearsal_created",
    "quarantine_release_path_present",
    "transform_to_broker_path_present",
    "unauthorized_artifact_mutation",
    "workflow_to_execution_bridge_present",
    "execution_artifacts_created",
    "browser_automation_added",
    "pageagent_added",
    "dom_extraction_added",
    "mined_repo_executed",
    "sports_source_activated",
]

STAGED_SAFE_TRUE_KEYS = [
    "read_only_only",
    "live_submit_disabled",
    "caps_unchanged",
    "quarantine_release_locked",
    "OPERATOR_ARMED_REHEARSAL_LOCKED",
    "QUARANTINE_RELEASE_LOCKED",
    "LIVE_TRADING_LOCKED",
    "LIVE_SUBMIT_DISABLED",
    "CAPS_OPERATOR_CONTROLLED",
]


def assert_staged_safe(report: dict[str, Any]) -> None:
    for key in STAGED_SAFE_FALSE_KEYS:
        assert report.get(key) is False, f"{key} must be False in {report.get('report_name')}"
    for key in STAGED_SAFE_TRUE_KEYS:
        assert report.get(key) is True, f"{key} must be True in {report.get('report_name')}"
