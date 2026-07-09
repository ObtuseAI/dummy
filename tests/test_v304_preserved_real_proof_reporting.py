"""Tests that v304 reports preserved real-proof state without inflating live-proof score."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.generate_v304_reports import generate_all_v304_reports_for_tests
from tests._real_proof_test_helpers import BACKUP_DIR_NAME, INDEX_NAME, make_evidence_bundle, patch_artifact_paths


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_v304_preserved_real_proof_reporting(monkeypatch, tmp_path):
    """v304 default state has no live proof, but preserved broker-rejection proof is reported."""
    root, registry_path, index_path, expected_index_hash = make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, root)

    d = generate_all_v304_reports_for_tests()[
        "v304_completion_lift_v10_controller_report.json"
    ]

    # Default state: no active live proof.
    assert d["active_default_state_real_first_live_proof_present"] is False
    assert d["real_first_live_proof_present"] is False

    # Preserved real-proof registry is surfaced, not inflated into an accepted order.
    assert d["preserved_real_broker_proof_present"] is True
    assert d["preserved_real_broker_proof_status"] == "BROKER_REJECTED"
    assert d["preserved_real_broker_contacted"] is True
    assert d["preserved_real_live_orders_submitted_count"] == 0
    assert d["preserved_broker_rejection_captured"] is True

    # Evidence index path/hash integrity.
    expected_index_rel = f"artifacts/dummy/{BACKUP_DIR_NAME}/{INDEX_NAME}"
    assert d["preserved_evidence_index_path"] == expected_index_rel
    assert d["preserved_evidence_index_hash"] == expected_index_hash
    assert d["preserved_evidence_index_hash"] == _sha256_file(index_path)

    # Scale and autonomy remain blocked in the active default state.
    percentages = d["subsystem_percentages"]
    assert percentages["scale_review"] == 0
    assert percentages["autonomy_review"] == 0
    assert d["scale_autonomy_blocked_by_no_live_proof"] is True
