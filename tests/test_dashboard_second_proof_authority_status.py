"""Tests for dashboard second-proof-authority status and action endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dashboard.backend import operator_control_routes as routes
from dashboard.backend.operator_control_routes import (
    SECOND_PROOF_REQUIRED_CONFIRMATION,
    _load_second_proof_authority_status,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def test_second_proof_authority_status_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.backend.operator_control_routes.SECOND_PROOF_DIR", tmp_path)
    status = _load_second_proof_authority_status()
    assert status["state"] == "absent"
    assert status["submit_allowed_now"] is False
    assert status["no_auto_live"] is True


def test_second_proof_authority_status_draft(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.backend.operator_control_routes.SECOND_PROOF_DIR", tmp_path)
    _write_json(
        tmp_path / "SECOND_PROOF_AUTHORITY_DRAFT.json",
        {
            "authority_id": "sp-draft-1",
            "authority_type": "SECOND_CONTROLLED_REAL_BROKER_PROOF",
            "status": "draft",
            "candidate_market_ticker": "KXACTIVE-S2026ABCD-1234",
            "candidate_contract_ticker": "KXACTIVE-S2026ABCD-1234",
            "candidate_price": 1,
            "candidate_count": 1,
            "candidate_order_type": "LIMIT",
        },
    )
    status = _load_second_proof_authority_status()
    assert status["state"] == "draft"
    assert status["authority_id"] == "sp-draft-1"
    assert status["candidate_price"] == 1
    assert status["submit_allowed_now"] is False
    assert status["next_action"].startswith("activate")


def test_second_proof_authority_status_active(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.backend.operator_control_routes.SECOND_PROOF_DIR", tmp_path)
    _write_json(
        tmp_path / "SECOND_PROOF_AUTHORITY_ACTIVE.json",
        {
            "authority_id": "sp-active-1",
            "authority_type": "SECOND_CONTROLLED_REAL_BROKER_PROOF",
            "status": "active",
            "candidate_market_ticker": "KXACTIVE-S2026ABCD-1234",
            "candidate_contract_ticker": "KXACTIVE-S2026ABCD-1234",
            "candidate_price": 1,
            "candidate_count": 1,
            "candidate_order_type": "LIMIT",
        },
    )
    status = _load_second_proof_authority_status()
    assert status["state"] == "active"
    assert status["authority_id"] == "sp-active-1"
    assert status["next_action"].startswith("arm")


def test_second_proof_authority_status_no_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.backend.operator_control_routes.SECOND_PROOF_DIR", tmp_path)
    _write_json(
        tmp_path / "SECOND_PROOF_AUTHORITY_DRAFT.json",
        {
            "authority_id": "sp-draft-1",
            "status": "draft",
            "api_key": "super-secret",
        },
    )
    status = _load_second_proof_authority_status()
    assert "api_key" not in status
    assert status["secrets_redacted"] is True


@pytest.mark.asyncio
async def test_prepare_endpoint_calls_script(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.backend.operator_control_routes.SECOND_PROOF_DIR", tmp_path)
    calls = []

    def fake_run(script, args, *, extra_env=None, timeout=120, safety_notes=None):
        calls.append((script, args))
        return {"ok": True, "stdout": "{}", "stderr": "", "safety_notes": safety_notes or []}

    monkeypatch.setattr("dashboard.backend.operator_control_routes._run_script", fake_run)
    result = await routes.second_proof_authority_prepare()
    assert result["ok"] is True
    assert any("prepare-second-proof-authority" in args for _, args in calls)


@pytest.mark.asyncio
async def test_activate_endpoint_refuses_mismatched_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.backend.operator_control_routes.SECOND_PROOF_DIR", tmp_path)
    calls = []

    def fake_run(script, args, *, extra_env=None, timeout=120, safety_notes=None):
        calls.append((script, args))
        return {"ok": True, "stdout": "{}", "stderr": "", "safety_notes": safety_notes or []}

    monkeypatch.setattr("dashboard.backend.operator_control_routes._run_script", fake_run)
    result = await routes.second_proof_authority_activate(
        routes.SecondProofAuthorityActivateBody(
            operator_name="op",
            reason="test",
            expires_at="2026-12-31T23:59:59Z",
            confirm="wrong confirmation",
        )
    )
    assert result["ok"] is False
    assert result["refused"] is True
    assert result["reason"] == "TYPED_CONFIRM_MISMATCH"
    assert not calls


@pytest.mark.asyncio
async def test_activate_endpoint_calls_script_with_exact_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.backend.operator_control_routes.SECOND_PROOF_DIR", tmp_path)
    calls = []

    def fake_run(script, args, *, extra_env=None, timeout=120, safety_notes=None):
        calls.append((script, args))
        return {"ok": True, "stdout": "{}", "stderr": "", "safety_notes": safety_notes or []}

    monkeypatch.setattr("dashboard.backend.operator_control_routes._run_script", fake_run)
    result = await routes.second_proof_authority_activate(
        routes.SecondProofAuthorityActivateBody(
            operator_name="op",
            reason="test",
            expires_at="2026-12-31T23:59:59Z",
            confirm=SECOND_PROOF_REQUIRED_CONFIRMATION,
        )
    )
    assert result["ok"] is True
    assert any(
        "activate-second-proof-authority" in args and "--confirm" in args and SECOND_PROOF_REQUIRED_CONFIRMATION in args
        for _, args in calls
    )
