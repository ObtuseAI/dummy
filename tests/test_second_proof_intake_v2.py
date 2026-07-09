"""Tests for second-proof evidence intake, reconciliation, and routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.second_proof_intake import (
    ROUTE_CLASSIFIED_REJECTION_NEW_AUTHORITY_REQUIRED,
    ROUTE_EVIDENCE_UNTRUSTED_QUARANTINE,
    ROUTE_NO_PROOF_TO_INGEST,
    ROUTE_POST_ACCEPTANCE_RECONCILE,
    ROUTE_PRE_BROKER_GATE_REPAIR,
    find_latest_second_proof_evidence,
    ingest_second_proof,
    write_route_report,
)


def _write_evidence(root: Path, name: str, payload: dict) -> Path:
    evidence_dir = root / name
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "SECOND_REAL_PROOF_EVIDENCE_REPORT.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return evidence_dir


def _base_evidence(**overrides) -> dict:
    base = {
        "authority_id": "second-proof-testauth00000001",
        "verdict": "SECOND_PROOF_EXECUTED_BROKER_REJECTED",
        "broker_contacted": True,
        "broker_accepted": False,
        "broker_rejected": True,
        "broker_order_id": "",
        "broker_rejection_code": None,
        "broker_rejection_http_status": None,
        "broker_rejection_safe_message": None,
        "broker_rejection_stage": None,
        "candidate_market_ticker": "KXTEST-INTAKE",
        "candidate_order_type": "LIMIT",
        "candidate_price": 1,
        "candidate_hash": "ABC123",
    }
    base.update(overrides)
    return base


def _write_lock(lock_dir: Path, authority_id: str, payload: dict) -> Path:
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / f"second_proof_{authority_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_no_evidence_routes_no_proof(tmp_path):
    report = ingest_second_proof(
        evidence_dir=None,
        lock_dir=tmp_path / "locks",
        v3_candidate_path=tmp_path / "v3.json",
        live_submit_path=tmp_path / "live_submit.json",
    )
    assert report["route"] == ROUTE_NO_PROOF_TO_INGEST


def test_pre_broker_gate_block_detected_and_flagged(tmp_path, monkeypatch):
    """The 2026-07-08 case: evidence claims contact, lock reason says the
    firewall blocked on live_submit_disabled, no transport witness exists."""
    monkeypatch.setenv("DUMMY_EVIDENCE_ROOT", str(tmp_path))
    evidence_dir = _write_evidence(tmp_path, "second_real_proof_20260708T205508", _base_evidence())
    _write_lock(
        tmp_path / "locks",
        "second-proof-testauth00000001",
        {
            "accepted": False,
            "rejected": True,
            "consumed": True,
            "broker_contacted": True,
            "reason": "live_submit_disabled",
            "broker_rejection_code": "",
        },
    )

    report = ingest_second_proof(
        evidence_dir=evidence_dir,
        lock_dir=tmp_path / "locks",
        v3_candidate_path=tmp_path / "v3.json",
        live_submit_path=tmp_path / "live_submit.json",
    )

    assert report["route"] == ROUTE_PRE_BROKER_GATE_REPAIR
    assert report["truth"]["witnessed_broker_contact"] is False
    assert report["truth"]["contact_claim_unsupported"] is True
    assert report["truth"]["classification"]["category"] == "PRE_BROKER_GATE"
    assert any("live_submit" in step for step in report["next_actions"])


def test_genuine_rejection_routes_new_authority(tmp_path):
    evidence_dir = _write_evidence(
        tmp_path,
        "second_real_proof_x",
        _base_evidence(
            broker_rejection_code="BROKER_VALIDATION",
            broker_rejection_http_status=400,
            broker_rejection_safe_message="market is closed",
            broker_rejection_stage="broker_transport",
        ),
    )
    _write_lock(
        tmp_path / "locks",
        "second-proof-testauth00000001",
        {"accepted": False, "rejected": True, "consumed": True, "reason": "BROKER_VALIDATION"},
    )
    report = ingest_second_proof(
        evidence_dir=evidence_dir,
        lock_dir=tmp_path / "locks",
        v3_candidate_path=tmp_path / "v3.json",
        live_submit_path=tmp_path / "live_submit.json",
    )
    assert report["route"] == ROUTE_CLASSIFIED_REJECTION_NEW_AUTHORITY_REQUIRED
    assert report["truth"]["classification"]["category"] == "MARKET_CLOSED"
    assert report["truth"]["contact_claim_unsupported"] is False


def test_acceptance_routes_reconcile(tmp_path):
    evidence_dir = _write_evidence(
        tmp_path,
        "second_real_proof_y",
        _base_evidence(
            verdict="SECOND_PROOF_EXECUTED_ACCEPTED",
            broker_accepted=True,
            broker_rejected=False,
            broker_order_id="ord-123",
        ),
    )
    _write_lock(
        tmp_path / "locks",
        "second-proof-testauth00000001",
        {"accepted": True, "rejected": False, "consumed": True, "reason": "accepted", "broker_order_id": "ord-123"},
    )
    report = ingest_second_proof(
        evidence_dir=evidence_dir,
        lock_dir=tmp_path / "locks",
        v3_candidate_path=tmp_path / "v3.json",
        live_submit_path=tmp_path / "live_submit.json",
    )
    assert report["route"] == ROUTE_POST_ACCEPTANCE_RECONCILE


def test_uncorroborated_evidence_is_quarantined(tmp_path):
    """Evidence with no runtime lock (e.g. written by a test double) must
    never route to acceptance — this is the fixture-inflation guard."""
    evidence_dir = _write_evidence(
        tmp_path,
        "second_real_proof_fixture",
        _base_evidence(
            verdict="SECOND_PROOF_EXECUTED_ACCEPTED",
            broker_accepted=True,
            broker_rejected=False,
            broker_order_id="ord-fake-fixture",
        ),
    )
    report = ingest_second_proof(
        evidence_dir=evidence_dir,
        lock_dir=tmp_path / "locks",
        v3_candidate_path=tmp_path / "v3.json",
        live_submit_path=tmp_path / "live_submit.json",
    )
    assert report["route"] == ROUTE_EVIDENCE_UNTRUSTED_QUARANTINE
    assert any("lock" in r for r in report["untrusted_reasons"])


def test_find_latest_prefers_newest_with_report(tmp_path):
    _write_evidence(tmp_path, "second_real_proof_20260708T111111", _base_evidence())
    newest = _write_evidence(tmp_path, "second_real_proof_20260708T222222", _base_evidence())
    (tmp_path / "second_real_proof_20260708T333333").mkdir()  # no report inside
    found = find_latest_second_proof_evidence(tmp_path)
    assert found == newest


def test_route_report_written_to_new_timestamped_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DUMMY_EVIDENCE_ROOT", str(tmp_path))
    evidence_dir = _write_evidence(tmp_path, "second_real_proof_z", _base_evidence())
    report = ingest_second_proof(
        evidence_dir=evidence_dir,
        lock_dir=tmp_path / "locks",
        v3_candidate_path=tmp_path / "v3.json",
        live_submit_path=tmp_path / "live_submit.json",
    )
    path = write_route_report(report)
    assert path.exists()
    assert path.name.startswith("SECOND_PROOF_ROUTE_REPORT_")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["mutates_canonical_state"] is False


def test_intake_never_mutates_inputs(tmp_path):
    evidence_dir = _write_evidence(tmp_path, "second_real_proof_w", _base_evidence())
    lock_path = _write_lock(tmp_path / "locks", "second-proof-testauth00000001", {"consumed": True, "reason": "live_submit_disabled"})
    evidence_before = (evidence_dir / "SECOND_REAL_PROOF_EVIDENCE_REPORT.json").read_bytes()
    lock_before = lock_path.read_bytes()

    ingest_second_proof(
        evidence_dir=evidence_dir,
        lock_dir=tmp_path / "locks",
        v3_candidate_path=tmp_path / "v3.json",
        live_submit_path=tmp_path / "live_submit.json",
    )

    assert (evidence_dir / "SECOND_REAL_PROOF_EVIDENCE_REPORT.json").read_bytes() == evidence_before
    assert lock_path.read_bytes() == lock_before
