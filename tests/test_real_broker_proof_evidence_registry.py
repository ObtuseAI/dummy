"""Tests for the preserved real-proof evidence registry and index integrity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests._real_proof_test_helpers import BACKUP_DIR_NAME, INDEX_NAME, make_evidence_bundle, patch_artifact_paths

FORBIDDEN_SECRET_SNIPPETS = (
    "KALSHI_API_KEY_ID",
    "BEGIN PRIVATE KEY",
    "SECRET",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_real_broker_proof_evidence_registry(monkeypatch, tmp_path):
    """Evidence index and registry are consistent, secret-free, and reflect broker rejection."""
    root, registry_path, index_path, expected_index_hash = make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, root)

    assert index_path.exists()
    assert registry_path.exists()

    index = json.loads(index_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    # Registry points at the evidence index.
    expected_index_rel = f"artifacts/dummy/{BACKUP_DIR_NAME}/{INDEX_NAME}"
    assert registry.get("latest_real_broker_proof_index") == expected_index_rel

    # Every source artifact hash recomputes correctly.
    assert isinstance(index.get("source_artifact_paths"), list)
    for entry in index["source_artifact_paths"]:
        src_path = root / entry["path"]
        assert src_path.exists(), f"Missing source artifact: {entry['path']}"
        recomputed = _sha256_file(src_path)
        assert recomputed == entry["sha256"].upper(), f"Hash mismatch for {entry['path']}"

    # Registry hash matches recomputed hash of the evidence index.
    assert registry.get("evidence_index_hash") == expected_index_hash

    # No secrets are serialized in either file.
    combined_text = json.dumps(index) + json.dumps(registry)
    for snippet in FORBIDDEN_SECRET_SNIPPETS:
        assert snippet not in combined_text, f"Secret snippet found in registry/index: {snippet}"

    # Registry reflects the preserved broker-rejection state.
    assert registry.get("latest_real_broker_attempt_status") == "BROKER_REJECTED"
    assert registry.get("latest_real_live_orders_submitted_count") == 0
    assert registry.get("latest_real_broker_contacted") is True


def test_actual_preserved_evidence_index_integrity():
    """The real preserved evidence index and backup artifacts are consistent and secret-free."""
    repo_root = Path(".")
    index_path = repo_root / "artifacts" / "dummy" / "real_proof_backup_20260707T1855" / INDEX_NAME
    registry_path = repo_root / "artifacts" / "dummy" / "real_proof_registry.json"
    assert index_path.exists(), "Preserved evidence index missing"
    assert registry_path.exists(), "Proof registry missing"

    index = json.loads(index_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    # Registry points at the actual evidence index.
    expected_index_rel = f"artifacts/dummy/{BACKUP_DIR_NAME}/{INDEX_NAME}"
    assert registry.get("latest_real_broker_proof_index") == expected_index_rel
    index_hash = hashlib.sha256(index_path.read_bytes()).hexdigest().upper()
    assert registry.get("evidence_index_hash") == index_hash

    # Every source artifact hash recomputes correctly.
    assert isinstance(index.get("source_artifact_paths"), list)
    for entry in index["source_artifact_paths"]:
        src_path = repo_root / entry["path"]
        assert src_path.exists(), f"Missing source artifact: {entry['path']}"
        recomputed = hashlib.sha256(src_path.read_bytes()).hexdigest().upper()
        assert recomputed == entry["sha256"].upper(), f"Hash mismatch for {entry['path']}"

    # No secrets in the actual index.
    combined_text = json.dumps(index) + json.dumps(registry)
    for snippet in FORBIDDEN_SECRET_SNIPPETS:
        assert snippet not in combined_text, f"Secret snippet found in registry/index: {snippet}"

    # Preserved state reflects a broker-rejected real attempt.
    assert index.get("real_broker_contacted") is True
    assert index.get("real_live_orders_submitted_count") == 0
    assert index.get("broker_rejection_captured") is True
    assert index.get("broker_order_id") is None
    assert index.get("submitted_live_order") is False
    assert index.get("accepted_by_broker") is False
    assert index.get("rejected_by_broker") is True
