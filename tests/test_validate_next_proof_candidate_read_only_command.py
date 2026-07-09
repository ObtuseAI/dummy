"""Focused tests for the read-only Kalshi metadata candidate CLI wiring.

These tests verify the `validate-next-proof-candidate` command in
`no-network` (V1) and `read-only` (V3 discovery) modes without contacting a real broker.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._real_proof_test_helpers import make_evidence_bundle, patch_artifact_paths
from tools.operator_authority_appliance import operator_full_completion as ofc

CLI = [sys.executable, "-m", "tools.operator_authority_appliance.operator_full_completion"]

V3_CANDIDATE_FILE = "VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json"
V3_REPORT_FILE = "NEXT_PROOF_CANDIDATE_DISCOVERY_V3_REPORT.json"


def _fake_candidate() -> SimpleNamespace:
    return SimpleNamespace(
        candidate_id="cand-123",
        created_at="2026-07-08T00:00:00+00:00",
        validation_mode="read_only_discovery",
        market_ticker="KXBTC-26DEC25000-C",
        contract_ticker="KXBTC-26DEC25000-C",
        market_status="open",
        contract_status="open",
        market_tradable=True,
        contract_tradable=True,
        price_source="metadata",
        price_validated=True,
        price=1,
        count=1,
        order_type="LIMIT",
        action="buy",
        side="yes",
        caps_hash="caps",
        descriptor_hash="desc",
        evidence_registry_hash="registry",
        proof_lock_status="consumed_by_real_broker_attempt",
        submit_allowed_now=False,
        requires_new_operator_proof_authority=True,
        reason_submit_not_allowed=ofc.PREVIOUS_REAL_BROKER_ATTEMPT_RECORDED,
        redacted=True,
        candidate_found=True,
        read_only_metadata_contact=True,
        broker_submit_contact=False,
        live_order_count=0,
        order_write_methods_blocked=True,
        metadata_mode="read_only_discovery",
        previous_real_broker_attempt_recorded=True,
        no_submit_performed=True,
        no_cancel_performed=True,
        no_live_submit_mutation=True,
        secrets_redacted=True,
        discovery_mode="broad",
        get_request_count=1,
        write_request_count=0,
        blocked_write_request_count=0,
        response_schema_summary="keys:cursor,markets",
        candidate_selection_trace=["live_eligible_candidate_found"],
        exact_blockers=[],
    )


def test_no_network_writes_v1_packet_and_report(tmp_path):
    make_evidence_bundle(tmp_path)
    out_dir = tmp_path / "next_proof_candidate"

    # Files whose mutation would indicate an unauthorized side-effect.
    configs = tmp_path / "configs"
    configs.mkdir()
    live_submit = configs / "live_submit.json"
    live_submit.write_text(json.dumps({"enabled": False}), encoding="utf-8")
    live_hash_before = hashlib.sha256(live_submit.read_bytes()).hexdigest()

    approvals = tmp_path / "runtime" / "approvals"
    approvals.mkdir(parents=True)
    approval = approvals / "operator.json"
    approval.write_text(json.dumps({"ok": True}), encoding="utf-8")
    approval_hash_before = hashlib.sha256(approval.read_bytes()).hexdigest()

    env = os.environ.copy()
    env["DUMMY_NEXT_PROOF_CANDIDATE_OUT_DIR"] = str(out_dir)
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate", "--mode", "no-network"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert result.returncode == 0, result.stderr

    v1 = out_dir / "VALIDATED_KALSHI_PROOF_CANDIDATE.json"
    report = out_dir / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"
    assert v1.exists()
    assert report.exists()

    data = json.loads(report.read_text())
    assert data["read_only_metadata_status"] == "not_used"
    assert data["submit_allowed_now"] is False
    assert data["requires_new_operator_proof_authority"] is True

    # No V2 artifacts are produced in no-network mode.
    assert not (out_dir / "VALIDATED_KALSHI_PROOF_CANDIDATE_V2.json").exists()
    assert not (out_dir / "NEXT_PROOF_CANDIDATE_READ_ONLY_METADATA_REPORT.json").exists()

    # No live-submit, caps, or approval mutation occurred.
    assert hashlib.sha256(live_submit.read_bytes()).hexdigest() == live_hash_before
    assert hashlib.sha256(approval.read_bytes()).hexdigest() == approval_hash_before


def test_network_mode_alias_maps_to_no_network(tmp_path):
    make_evidence_bundle(tmp_path)
    out_dir = tmp_path / "next_proof_candidate"
    env = os.environ.copy()
    env["DUMMY_NEXT_PROOF_CANDIDATE_OUT_DIR"] = str(out_dir)
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate", "--network-mode=no_network"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    report = out_dir / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"
    assert report.exists()
    data = json.loads(report.read_text())
    assert data["read_only_metadata_status"] == "not_used"


def test_read_only_active_market_writes_v3_packet_and_report(tmp_path, monkeypatch):
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    out_dir = tmp_path / "next_proof_candidate"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create V1/V2 packets to confirm they are not touched when V3 is written.
    v1 = out_dir / "VALIDATED_KALSHI_PROOF_CANDIDATE.json"
    v1.write_text(json.dumps({"version": 1}), encoding="utf-8")
    v1_hash_before = hashlib.sha256(v1.read_bytes()).hexdigest()
    v2 = out_dir / "VALIDATED_KALSHI_PROOF_CANDIDATE_V2.json"
    v2.write_text(json.dumps({"version": 2}), encoding="utf-8")
    v2_hash_before = hashlib.sha256(v2.read_bytes()).hexdigest()

    monkeypatch.setattr(ofc.env_loader, "read_whitelisted_env", lambda _path: {"KALSHI_API_KEY_ID": "kid"})
    monkeypatch.setattr(ofc, "kalshi_credential_status", lambda _values=None: {
        "KALSHI_API_KEY_ID": {"present": True},
        "KALSHI_API_PRIVATE_KEY_PEM": {"present": True},
    })

    class FakeReadOnlyClient:
        request_audit_log = []
        blocked_attempts = []

        def http_summary(self):
            return {"total_requests": 1, "methods": {"GET": 1}}

    monkeypatch.setattr(ofc.kalshi_market_validator, "KalshiReadOnlyMetadataClient", FakeReadOnlyClient)

    metadata = ofc.kalshi_market_validator.MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="open",
        open_time=None,
        close_time=None,
        trading_allowed=True,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[
            ofc.kalshi_market_validator.ContractMetadata(
                ticker="KXBTC-26DEC25000-C", status="open", tradable=True
            )
        ],
    )
    monkeypatch.setattr(
        ofc.kalshi_market_validator,
        "discover_live_eligible_candidates",
        lambda client, max_candidates=10, prefer_event=None: (True, metadata, "ok"),
    )
    monkeypatch.setattr(ofc.kalshi_market_validator, "derive_validated_price", lambda _metadata: (1, True, "ok"))

    candidate = _fake_candidate()
    monkeypatch.setattr(ofc.proof_order_candidate, "build_validated_proof_candidate_v3", lambda *a, **kw: candidate)
    monkeypatch.setattr(
        ofc.proof_order_candidate,
        "write_candidate_packet_v3",
        lambda cand, path: Path(path).write_text(
            json.dumps(cand.__dict__, indent=2), encoding="utf-8"
        ),
    )

    rc = ofc.main(
        [
            "validate-next-proof-candidate",
            "--mode",
            "read-only",
            "--allow-read-only-kalshi-get",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert rc == 0

    v3 = out_dir / V3_CANDIDATE_FILE
    report = out_dir / V3_REPORT_FILE
    assert v3.exists()
    assert report.exists()

    data = json.loads(report.read_text())
    assert data["verdict"] == "READ_ONLY_DISCOVERY_V3_CANDIDATE_FOUND"
    assert data["candidate_found"] is True
    assert data["discovery_mode"] == "broad"
    assert data["read_only_kalshi_metadata_contact"] is True
    assert data["broker_submit_contact_during_validation"] is False
    assert data["live_order_count_during_validation"] == 0
    assert data["submit_allowed_now"] is False
    assert data["requires_new_operator_proof_authority"] is True
    assert data["reason_submit_not_allowed"] == ofc.PREVIOUS_REAL_BROKER_ATTEMPT_RECORDED

    # V1/V2 packets remain untouched.
    assert v1.exists()
    assert hashlib.sha256(v1.read_bytes()).hexdigest() == v1_hash_before
    assert v2.exists()
    assert hashlib.sha256(v2.read_bytes()).hexdigest() == v2_hash_before


def test_read_only_missing_flag_blocked(tmp_path, monkeypatch):
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    out_dir = tmp_path / "next_proof_candidate"

    rc = ofc.main(
        ["validate-next-proof-candidate", "--mode", "read-only", "--out-dir", str(out_dir)]
    )
    assert rc == 0

    report = out_dir / V3_REPORT_FILE
    assert report.exists()
    data = json.loads(report.read_text())
    assert data["verdict"] == "READ_ONLY_DISCOVERY_V3_NO_CANDIDATE"
    assert ofc.MISSING_READ_ONLY_GET_APPROVAL_FLAG in data["exact_blockers"]
    assert data["candidate_found"] is False
    assert data["no_submit_performed"] is True
    assert data["no_cancel_performed"] is True


def test_read_only_missing_credentials_blocked(tmp_path, monkeypatch):
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    out_dir = tmp_path / "next_proof_candidate"

    monkeypatch.setattr(ofc.env_loader, "read_whitelisted_env", lambda _path: {})
    monkeypatch.setattr(ofc, "kalshi_credential_status", lambda _values=None: {
        "KALSHI_API_KEY_ID": {"present": False},
        "KALSHI_API_PRIVATE_KEY_PEM": {"present": False},
    })

    rc = ofc.main(
        [
            "validate-next-proof-candidate",
            "--mode",
            "read-only",
            "--allow-read-only-kalshi-get",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert rc == 0

    data = json.loads((out_dir / V3_REPORT_FILE).read_text())
    assert data["verdict"] == "READ_ONLY_DISCOVERY_V3_NO_CANDIDATE"
    assert ofc.KALSHI_CREDENTIALS_MISSING in data["exact_blockers"]
    assert data["candidate_found"] is False


def test_read_only_closed_market_rejected(tmp_path, monkeypatch):
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    out_dir = tmp_path / "next_proof_candidate"

    monkeypatch.setattr(ofc.env_loader, "read_whitelisted_env", lambda _path: {"KALSHI_API_KEY_ID": "kid"})
    monkeypatch.setattr(ofc, "kalshi_credential_status", lambda _values=None: {
        "KALSHI_API_KEY_ID": {"present": True},
        "KALSHI_API_PRIVATE_KEY_PEM": {"present": True},
    })

    class FakeReadOnlyClient:
        request_audit_log = []
        blocked_attempts = []

        def http_summary(self):
            return {"total_requests": 1, "methods": {"GET": 1}}

    monkeypatch.setattr(ofc.kalshi_market_validator, "KalshiReadOnlyMetadataClient", FakeReadOnlyClient)
    monkeypatch.setattr(
        ofc.kalshi_market_validator,
        "discover_live_eligible_candidates",
        lambda client, max_candidates=10, prefer_event=None: (False, None, "NO_TRADABLE_MARKETS"),
    )

    rc = ofc.main(
        [
            "validate-next-proof-candidate",
            "--mode",
            "read-only",
            "--allow-read-only-kalshi-get",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert rc == 0

    data = json.loads((out_dir / V3_REPORT_FILE).read_text())
    assert data["verdict"] == "READ_ONLY_DISCOVERY_V3_NO_CANDIDATE"
    assert data["candidate_found"] is False
    assert "NO_TRADABLE_MARKETS" in data["exact_blockers"]
    assert data["no_submit_performed"] is True
    assert data["no_cancel_performed"] is True
    assert data["broker_submit_contact_during_validation"] is False
    assert data["live_order_count_during_validation"] == 0


def test_read_only_explicit_closed_market_rejected(tmp_path, monkeypatch):
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    out_dir = tmp_path / "next_proof_candidate"

    monkeypatch.setattr(ofc.env_loader, "read_whitelisted_env", lambda _path: {"KALSHI_API_KEY_ID": "kid"})
    monkeypatch.setattr(ofc, "kalshi_credential_status", lambda _values=None: {
        "KALSHI_API_KEY_ID": {"present": True},
        "KALSHI_API_PRIVATE_KEY_PEM": {"present": True},
    })

    closed_metadata = ofc.kalshi_market_validator.MarketMetadata(
        ticker="KXBTC-26DEC25000-C",
        status="closed",
        open_time=None,
        close_time=None,
        trading_allowed=False,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[
            ofc.kalshi_market_validator.ContractMetadata(
                ticker="KXBTC-26DEC25000-C", status="closed", tradable=False
            )
        ],
    )

    class FakeClient:
        request_audit_log = []
        blocked_attempts = []

        def http_summary(self):
            return {"total_requests": 1, "methods": {"GET": 1}}

        def get_market(self, ticker: str):
            return closed_metadata

    monkeypatch.setattr(ofc.kalshi_market_validator, "KalshiReadOnlyMetadataClient", FakeClient)

    rc = ofc.main(
        [
            "validate-next-proof-candidate",
            "--mode",
            "read-only",
            "--allow-read-only-kalshi-get",
            "--market-ticker",
            "KXBTC-26DEC25000-C",
            "--out-dir",
            str(out_dir),
        ]
    )
    assert rc == 0

    data = json.loads((out_dir / V3_REPORT_FILE).read_text())
    assert data["verdict"] == "READ_ONLY_DISCOVERY_V3_NO_CANDIDATE"
    assert data["candidate_found"] is False
    assert data["discovery_mode"] == "explicit"
    assert any("MARKET_NOT_OPEN" in b for b in data["exact_blockers"])
    assert data["no_submit_performed"] is True
    assert data["no_cancel_performed"] is True
