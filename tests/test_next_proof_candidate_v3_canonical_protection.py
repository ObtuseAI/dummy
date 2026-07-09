"""Canonical V3 candidate/discovery artifact protection tests.

The optional read-only freshness check previously overwrote the canonical V3 files
(``VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json`` and
``NEXT_PROOF_CANDIDATE_DISCOVERY_V3_REPORT.json``) with a failed validation packet.
These tests ensure that cannot happen again without an explicit promotion flag.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._real_proof_test_helpers import make_evidence_bundle, patch_artifact_paths
from tools.operator_authority_appliance import operator_full_completion as ofc

CANDIDATE_FILE = "VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json"
REPORT_FILE = "NEXT_PROOF_CANDIDATE_DISCOVERY_V3_REPORT.json"


def _canonical_dir(tmp_path: Path) -> Path:
    """Return the canonical next-proof-candidate directory for a test cwd."""
    return tmp_path / "artifacts" / "dummy" / "next_proof_candidate"


def _seed_canonical(canonical: Path) -> tuple[str, str]:
    """Create canonical V3 files with known content and return their hashes."""
    canonical.mkdir(parents=True, exist_ok=True)
    candidate_path = canonical / CANDIDATE_FILE
    report_path = canonical / REPORT_FILE
    candidate_path.write_text(json.dumps({"canonical": "candidate"}, sort_keys=True), encoding="utf-8")
    report_path.write_text(json.dumps({"canonical": "report"}, sort_keys=True), encoding="utf-8")
    cand_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest().upper()
    rep_hash = hashlib.sha256(report_path.read_bytes()).hexdigest().upper()
    return cand_hash, rep_hash


def _patch_read_only_success(monkeypatch, tmp_path):
    """Patch the read-only Kalshi path so discovery succeeds with one GET."""
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

    candidate = SimpleNamespace(
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
        discovery_mode="explicit",
        get_request_count=1,
        write_request_count=0,
        blocked_write_request_count=0,
        response_schema_summary="keys:cursor,markets",
        candidate_selection_trace=["live_eligible_candidate_found"],
        exact_blockers=[],
        runtime_approval_hash="runtime-hash",
        current_live_submit_hash="live-submit-hash",
    )
    monkeypatch.setattr(ofc.proof_order_candidate, "build_validated_proof_candidate_v3", lambda *a, **kw: candidate)
    monkeypatch.setattr(
        ofc.proof_order_candidate,
        "write_candidate_packet_v3",
        lambda cand, path: Path(path).write_text(json.dumps(cand.__dict__, indent=2), encoding="utf-8"),
    )


def _args(*, promote: bool = False, out_dir: str | None = None) -> argparse.Namespace:
    # market_ticker=None triggers broad discovery, which is easier to mock.
    return argparse.Namespace(
        mode="read-only",
        market_ticker=None,
        contract_ticker=None,
        max_candidates=10,
        prefer_event=None,
        allow_read_only_kalshi_get=True,
        out_dir=out_dir,
        promote_freshness_to_canonical=promote,
    )


def test_read_only_failure_does_not_overwrite_canonical_v3(tmp_path, monkeypatch):
    """A failed read-only freshness check must leave canonical V3 files untouched."""
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    canonical = _canonical_dir(tmp_path)
    cand_hash_before, rep_hash_before = _seed_canonical(canonical)

    # Force read-only discovery to fail by missing credentials.
    monkeypatch.setattr(ofc, "kalshi_credential_status", lambda _values=None: {
        "KALSHI_API_KEY_ID": {"present": False},
    })

    out = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = out
    try:
        rc = ofc.cmd_validate_next_proof_candidate(_args())
    finally:
        sys.stdout = old_stdout
    assert rc == 0

    candidate_path = canonical / CANDIDATE_FILE
    report_path = canonical / REPORT_FILE
    assert hashlib.sha256(candidate_path.read_bytes()).hexdigest().upper() == cand_hash_before
    assert hashlib.sha256(report_path.read_bytes()).hexdigest().upper() == rep_hash_before

    freshness_dirs = [p for p in (canonical / "freshness_checks").glob("*") if p.is_dir()]
    assert len(freshness_dirs) >= 1


def test_read_only_success_does_not_promote_to_canonical_by_default(tmp_path, monkeypatch):
    """A successful read-only check must not overwrite canonical V3 without the promotion flag."""
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    canonical = _canonical_dir(tmp_path)
    cand_hash_before, rep_hash_before = _seed_canonical(canonical)

    _patch_read_only_success(monkeypatch, tmp_path)

    out = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = out
    try:
        rc = ofc.cmd_validate_next_proof_candidate(_args())
    finally:
        sys.stdout = old_stdout
    assert rc == 0

    candidate_path = canonical / CANDIDATE_FILE
    report_path = canonical / REPORT_FILE
    assert hashlib.sha256(candidate_path.read_bytes()).hexdigest().upper() == cand_hash_before
    assert hashlib.sha256(report_path.read_bytes()).hexdigest().upper() == rep_hash_before

    freshness_dirs = [p for p in (canonical / "freshness_checks").glob("*") if p.is_dir()]
    assert len(freshness_dirs) >= 1
    assert (freshness_dirs[0] / CANDIDATE_FILE).exists()
    assert (freshness_dirs[0] / REPORT_FILE).exists()


def test_canonical_promotion_writes_to_canonical_with_flag(tmp_path, monkeypatch):
    """``--promote-freshness-to-canonical`` allows an explicit canonical overwrite."""
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    canonical = _canonical_dir(tmp_path)
    _seed_canonical(canonical)
    _patch_read_only_success(monkeypatch, tmp_path)

    out = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = out
    try:
        rc = ofc.cmd_validate_next_proof_candidate(_args(promote=True))
    finally:
        sys.stdout = old_stdout
    assert rc == 0

    # With promotion, canonical files are refreshed.
    assert (canonical / CANDIDATE_FILE).exists()
    assert (canonical / REPORT_FILE).exists()
    data = json.loads((canonical / CANDIDATE_FILE).read_text())
    assert data["candidate_id"] == "cand-123"


def test_canonical_promotion_requires_explicit_flag(tmp_path, monkeypatch):
    """Default behavior must use a freshness_checks subdirectory, not canonical."""
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    canonical = _canonical_dir(tmp_path)
    _seed_canonical(canonical)
    _patch_read_only_success(monkeypatch, tmp_path)

    out = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = out
    try:
        rc = ofc.cmd_validate_next_proof_candidate(_args())
    finally:
        sys.stdout = old_stdout
    assert rc == 0

    # Default path was freshness_checks, not canonical.
    freshness_dirs = [p for p in (canonical / "freshness_checks").glob("*") if p.is_dir()]
    assert len(freshness_dirs) >= 1


def test_freshness_check_uses_get_only_no_write_methods(tmp_path, monkeypatch):
    """Read-only freshness must not use POST/PUT/PATCH/DELETE."""
    make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    _patch_read_only_success(monkeypatch, tmp_path)

    out = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = out
    try:
        rc = ofc.cmd_validate_next_proof_candidate(_args())
    finally:
        sys.stdout = old_stdout
    assert rc == 0

    canonical = _canonical_dir(tmp_path)
    freshness_dirs = [p for p in (canonical / "freshness_checks").glob("*") if p.is_dir()]
    assert len(freshness_dirs) == 1
    report_path = freshness_dirs[0] / REPORT_FILE
    data = json.loads(report_path.read_text())
    assert data["write_request_count"] == 0
    assert data["blocked_write_request_count"] == 0
    assert data["get_request_count"] >= 1
