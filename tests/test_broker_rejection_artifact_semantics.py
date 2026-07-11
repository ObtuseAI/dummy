"""Tests that v298 captures a structured broker rejection safely in the artifact."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from core.ontology import LiveOrderResult
from predator_mesh.v298.reports import full_authority_arm
from archive.report_scripts.generate_v298_reports import generate_all_v298_reports_for_tests
from tests._real_proof_test_helpers import BACKUP_DIR_NAME


def _patch_live_mode(monkeypatch):
    """Make the mode classifier think the environment is in one-proof live-ready state."""
    future = "2099-01-01T00:00:00Z"
    cfg = {
        "enabled": True,
        "operator": "chris",
        "reason": "test",
        "timestamp": future,
        "expiry": future,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "explicit_acknowledgement": "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only",
    }
    monkeypatch.setattr("predator_mesh.v298.reports._load_live_submit_config", lambda: cfg)
    monkeypatch.setattr("predator_mesh.v298.reports._caps_strict", lambda: True)
    monkeypatch.setattr("predator_mesh.v298.reports._descriptor_staged", lambda: True)
    monkeypatch.setattr("predator_mesh.v298.reports._command_seal_ready", lambda: True)
    monkeypatch.setattr("predator_mesh.v298.reports._proof_lock_clear", lambda: True)
    monkeypatch.setattr("predator_mesh.v298.reports._kalshi_credentials_ready", lambda: True)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "1")
    monkeypatch.setenv("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")


def test_broker_rejection_artifact_semantics(monkeypatch, tmp_path):
    """A structured broker rejection is recorded safely and never treated as an accepted order."""
    _patch_live_mode(monkeypatch)

    submit_mock = AsyncMock(
        return_value=LiveOrderResult(
            success=False,
            order_id=None,
            error="BROKER_REJECTED",
            proof_reference="",
            broker_rejection_code="BROKER_REJECTED",
            broker_rejection_safe_message="price too low",
            broker_rejection_http_status=400,
            broker_rejection_adapter_error_type="httpx.HTTPStatusError",
            broker_rejection_stage="broker_transport",
            broker_rejection_raw_redacted={
                "status_code": 400,
                "error_preview": "price too low",
                "adapter_error_type": "httpx.HTTPStatusError",
                "stage": "broker_transport",
            },
        )
    )
    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", submit_mock)

    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]

    # Core rejection semantics.
    assert d["real_broker_contacted"] is True
    assert d["real_live_orders_submitted_count"] == 0
    assert d.get("submitted_live_order", False) is False
    assert d.get("accepted_by_broker", d["real_live_orders_submitted_count"] > 0) is False
    assert d.get("rejected_by_broker", d["broker_rejection_captured"]) is True
    assert d["broker_rejection_captured"] is True
    assert d["proof_is_real"] is True

    # Structured diagnostics are preserved and safe.
    assert d["broker_rejection_code"] == "BROKER_REJECTED"
    assert d["broker_rejection_safe_message"] == "price too low"
    assert d["broker_rejection_http_status"] == 400
    assert d["broker_rejection_adapter_error_type"] == "httpx.HTTPStatusError"
    assert d["broker_rejection_stage"] == "broker_transport"

    # No retry: exactly one attempt and one adapter call.
    assert d["max_attempts"] == 1
    assert submit_mock.await_count == 1

    # Persist the report to a historical backup location and verify it reads back correctly.
    backup_dir = tmp_path / "artifacts" / "dummy" / BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / "v298_execute_once_final_proof_runner_v7_controller_report.json"
    backup_path.write_text(json.dumps(d, indent=2), encoding="utf-8")

    historical = json.loads(backup_path.read_text(encoding="utf-8"))
    assert historical["broker_rejection_captured"] is True
    assert historical["real_broker_contacted"] is True
