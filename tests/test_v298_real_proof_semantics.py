"""Tests for v298 real-proof artifact semantics."""

from __future__ import annotations


from core.live_submit_state import build_caps_authority_binding
from predator_mesh.v298.reports import full_authority_arm
from archive.report_scripts.generate_v298_reports import generate_all_v298_reports_for_tests
from tests.caps_authority_test_helpers import registered_caps_status


CAPS_AUTHORITY = registered_caps_status()


def _patch_live_mode(monkeypatch):
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
    monkeypatch.setattr("predator_mesh.v298.reports._load_live_submit_config", lambda: cfg)
    monkeypatch.setattr("predator_mesh.v298.reports._caps_strict", lambda: True)
    monkeypatch.setattr("predator_mesh.v298.reports._descriptor_staged", lambda: True)
    monkeypatch.setattr("predator_mesh.v298.reports._command_seal_ready", lambda: True)
    monkeypatch.setattr("predator_mesh.v298.reports._proof_lock_clear", lambda: True)
    monkeypatch.setattr("predator_mesh.v298.reports._kalshi_credentials_ready", lambda: True)
    monkeypatch.setenv("DUMMY_LIVE_PROOF_MODE", "1")
    monkeypatch.setenv("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")


def test_no_secret_values_in_artifact(monkeypatch, tmp_path):
    _patch_live_mode(monkeypatch)
    monkeypatch.setenv("KALSHI_API_KEY_ID", "secret-key-id-123")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", "-----BEGIN PRIVATE KEY-----\nSECRET\n-----END PRIVATE KEY-----")

    calls = []

    async def fake_submit(_self, _req):
        calls.append(_req)
        raise AssertionError("retired v298 runner must not call the compatibility submit adapter")

    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", fake_submit)

    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]
    text = str(d)
    assert "secret-key-id-123" not in text
    assert "-----BEGIN PRIVATE KEY-----" not in text
    assert "SECRET" not in text
    assert calls == []


def test_market_order_never_submitted(monkeypatch, tmp_path):
    _patch_live_mode(monkeypatch)
    calls = []

    async def fake_submit(_self, req):
        calls.append(req)
        raise AssertionError("retired v298 runner must not call the compatibility submit adapter")

    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", fake_submit)

    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]
    assert d["market_order_submitted"] is False
    assert calls == []


def test_idempotency_key_present_in_retired_report_without_submit(monkeypatch, tmp_path):
    _patch_live_mode(monkeypatch)
    calls = []

    async def fake_submit(_self, req):
        calls.append(req)
        raise AssertionError("retired v298 runner must not call the compatibility submit adapter")

    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", fake_submit)

    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]
    assert d["idempotency_key"]
    assert len(d["idempotency_key"]) == 32
    assert calls == []


def test_max_one_order(monkeypatch, tmp_path):
    _patch_live_mode(monkeypatch)
    calls = []

    async def fake_submit(_self, req):
        calls.append(req)
        raise AssertionError("retired v298 runner must not call the compatibility submit adapter")

    monkeypatch.setattr("live_firewall.firewall.LiveBrokerFirewall.submit_limit_order_adapter", fake_submit)

    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())[
        "v298_execute_once_final_proof_runner_v7_controller_report.json"
    ]
    assert d["real_live_orders_submitted_count"] == 0
    assert d["max_attempts"] == 1
    assert calls == []
