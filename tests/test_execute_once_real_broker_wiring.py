"""Tests that v298 runner wires to the real broker adapter path only in live mode."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v298.reports import full_authority_arm
from archive.report_scripts.generate_v298_reports import generate_all_v298_reports_for_tests


def _patch_live_mode(monkeypatch, live_submit_enabled: bool = True, credentials_ready: bool = True):
    """Make the mode classifier think the environment is in one-proof live-ready state."""
    future = "2099-01-01T00:00:00Z"
    cfg = {
        "enabled": live_submit_enabled,
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
    monkeypatch.setattr("predator_mesh.v298.reports._kalshi_credentials_ready", lambda: credentials_ready)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "1")
    monkeypatch.setenv("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")


def test_rehearsal_double_cannot_claim_real_proof(monkeypatch, tmp_path):
    """When env/config are NOT live-ready, the full-authority arm packet is treated as a rehearsal double."""
    monkeypatch.setattr("predator_mesh.v298.reports._load_live_submit_config", lambda: {"enabled": False})
    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]
    assert d["execute_once_final_proof_runner_v7_controller_status"] == "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
    assert d["uses_non_broker_double"] is True
    assert d["non_broker_double_used"] is True
    assert d["real_broker_contacted"] is False
    assert d["real_live_orders_submitted_count"] == 0
    assert d["proof_is_real"] is False


def test_live_mode_attempts_real_submit_and_records_accepted(monkeypatch, tmp_path):
    _patch_live_mode(monkeypatch)

    fake_result = {"success": True, "order_id": "ord-live-123", "error": None, "proof_reference": ""}

    async def fake_submit(_self, _req):
        from core.ontology import LiveOrderResult
        return LiveOrderResult(**fake_result)

    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", fake_submit)

    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]
    assert d["execute_once_final_proof_runner_v7_controller_status"] == "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
    assert d["uses_non_broker_double"] is False
    assert d["non_broker_double_used"] is False
    assert d["real_broker_contacted"] is True
    assert d["real_live_orders_submitted_count"] == 1
    assert d["broker_order_id"] == "ord-live-123"
    assert d["proof_is_real"] is True


def test_live_mode_captures_broker_rejection(monkeypatch, tmp_path):
    _patch_live_mode(monkeypatch)

    async def fake_submit(_self, _req):
        from core.ontology import LiveOrderResult
        return LiveOrderResult(success=False, order_id=None, error="BROKER_REJECTED", proof_reference="")

    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", fake_submit)

    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]
    assert d["real_broker_contacted"] is True
    assert d["real_live_orders_submitted_count"] == 0
    assert d["broker_rejection_captured"] is True
    assert d["broker_rejection_reason"] == "BROKER_REJECTED"
    assert d["broker_rejection_code"] == "BROKER_REJECTED"
    assert d["broker_rejection_safe_message"] is None
    assert d["proof_is_real"] is True


def test_live_mode_blocked_before_broker_when_caps_not_strict(monkeypatch, tmp_path):
    _patch_live_mode(monkeypatch)
    monkeypatch.setattr("predator_mesh.v298.reports._caps_strict", lambda: False)

    calls = []

    async def fake_submit(_self, _req):
        calls.append(True)
        from core.ontology import LiveOrderResult
        return LiveOrderResult(success=True, order_id="x", error=None, proof_reference="")

    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", fake_submit)

    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]
    assert d["uses_non_broker_double"] is True
    assert d["real_broker_contacted"] is False
    assert d["real_live_orders_submitted_count"] == 0
    assert len(calls) == 0
