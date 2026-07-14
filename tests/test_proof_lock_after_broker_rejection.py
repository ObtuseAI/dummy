"""Tests that the real-proof lock blocks a second v298 live attempt."""

from __future__ import annotations

from unittest.mock import AsyncMock


from core.proof_lock import proof_lock_clear
from predator_mesh.v298.reports import full_authority_arm
from archive.report_scripts.generate_v298_reports import generate_all_v298_reports_for_tests
from tests._real_proof_test_helpers import make_evidence_bundle, patch_artifact_paths


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
    # Do NOT patch _proof_lock_clear: the preserved registry should make it return False.
    monkeypatch.setattr("predator_mesh.v298.reports._kalshi_credentials_ready", lambda: True)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "1")
    monkeypatch.setenv("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")


def test_proof_lock_blocks_second_live_attempt(monkeypatch, tmp_path):
    """A preserved real-proof registry blocks another v298 live attempt before the adapter."""
    root, registry_path, *_ = make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, root)

    _patch_live_mode(monkeypatch)

    submit_mock = AsyncMock(return_value=None)
    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", submit_mock)

    # Arm everything except the proof-lock check so the ARM_CHECKS mapping fires.
    arm = full_authority_arm()
    arm["proof_lock_clear"] = False

    d = generate_all_v298_reports_for_tests(arm=arm)[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]

    assert d["execute_once_final_proof_runner_v7_controller_status"] == "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_STALE_PROOF_LOCK"
    assert submit_mock.await_count == 0
    assert d["real_broker_contacted"] is False
    assert d["real_live_orders_submitted_count"] == 0

    # Hiding the registry makes the lock clear, because the v298 final report is default-dry.
    assert proof_lock_clear() is False
    hidden = registry_path.with_suffix(".json.hidden")
    registry_path.rename(hidden)
    try:
        assert proof_lock_clear() is True
    finally:
        hidden.rename(registry_path)

    # Restoring the registry re-engages the lock.
    assert proof_lock_clear() is False
