"""Tests that v298 captures a structured broker rejection safely in the artifact."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock


from core.live_submit_state import build_caps_authority_binding
from predator_mesh.operator_proof_stages.execute_once import full_authority_arm
from predator_mesh.operator_proof_workflows import generate_execute_once_reports_for_tests as generate_all_v298_reports_for_tests
from tests._real_proof_test_helpers import BACKUP_DIR_NAME
from tests.caps_authority_test_helpers import registered_caps_status


CAPS_AUTHORITY = registered_caps_status()


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
        **build_caps_authority_binding(CAPS_AUTHORITY),
    }
    monkeypatch.setattr(
        "core.live_submit_state.evaluate_caps_authority",
        lambda: CAPS_AUTHORITY,
    )
    monkeypatch.setattr("predator_mesh.operator_proof_stages.execute_once._load_live_submit_config", lambda: cfg)
    monkeypatch.setattr("predator_mesh.operator_proof_stages.execute_once._caps_strict", lambda: True)
    monkeypatch.setattr("predator_mesh.operator_proof_stages.execute_once._descriptor_staged", lambda: True)
    monkeypatch.setattr("predator_mesh.operator_proof_stages.execute_once._command_seal_ready", lambda: True)
    monkeypatch.setattr("predator_mesh.operator_proof_stages.execute_once._proof_lock_clear", lambda: True)
    monkeypatch.setattr("predator_mesh.operator_proof_stages.execute_once._kalshi_credentials_ready", lambda: True)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "1")
    monkeypatch.setenv("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")


def test_broker_rejection_artifact_semantics(monkeypatch, tmp_path):
    """A retired runner cannot fabricate broker-contact evidence from a mock."""
    _patch_live_mode(monkeypatch)

    submit_mock = AsyncMock(side_effect=AssertionError("retired runner must not submit"))
    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", submit_mock)

    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]

    # Core no-contact semantics.
    assert d["execute_once_final_proof_runner_v7_controller_status"] == (
        "PARTIAL_EXECUTE_ONCE_FINAL_PROOF_RUNNER_RETIRED_CENTRAL_FIREWALL_REQUIRED"
    )
    assert d["arm_state"] == "BLOCKED_LEGACY_RUNNER_RETIRED"
    assert d["real_broker_contacted"] is False
    assert d["real_live_orders_submitted_count"] == 0
    assert d.get("submitted_live_order", False) is False
    assert d.get("accepted_by_broker", d["real_live_orders_submitted_count"] > 0) is False
    assert d.get("rejected_by_broker", d["broker_rejection_captured"]) is False
    assert d["broker_rejection_captured"] is False
    assert d["proof_is_real"] is False

    # No mock-provided diagnostics may masquerade as broker evidence.
    assert d["broker_rejection_code"] is None
    assert d["broker_rejection_safe_message"] is None
    assert d["broker_rejection_http_status"] is None
    assert d["broker_rejection_adapter_error_type"] is None
    assert d["broker_rejection_stage"] is None

    # No retry and no adapter call.
    assert d["max_attempts"] == 1
    assert submit_mock.await_count == 0

    # Persist the report to a historical backup location and verify it reads back correctly.
    backup_dir = tmp_path / "artifacts" / "dummy" / BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / "v298_execute_once_final_proof_runner_v7_controller_report.json"
    backup_path.write_text(json.dumps(d, indent=2), encoding="utf-8")

    historical = json.loads(backup_path.read_text(encoding="utf-8"))
    assert historical["broker_rejection_captured"] is False
    assert historical["real_broker_contacted"] is False
