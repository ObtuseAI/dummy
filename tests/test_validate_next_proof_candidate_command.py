import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests._real_proof_test_helpers import make_evidence_bundle, patch_artifact_paths

CLI = [sys.executable, "-m", "tools.operator_authority_appliance.operator_full_completion"]


def test_validate_next_proof_candidate_writes_report(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    out_dir = tmp_path / "next_proof_candidate"
    monkeypatch.setenv("DUMMY_NEXT_PROOF_CANDIDATE_OUT_DIR", str(out_dir))
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    report = out_dir / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"
    assert report.exists()
    data = json.loads(report.read_text())
    assert data["submit_allowed_now"] is False
    assert data["requires_new_operator_proof_authority"] is True


def test_validate_next_proof_candidate_does_not_enable_live_submit(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    live_submit = Path("configs/live_submit.json")
    if live_submit.exists():
        config = json.loads(live_submit.read_text())
        assert config.get("enabled") is not True


def test_validate_next_proof_candidate_no_broker_contact(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path)
    patch_artifact_paths(monkeypatch, tmp_path)
    out_dir = tmp_path / "next_proof_candidate"
    monkeypatch.setenv("DUMMY_NEXT_PROOF_CANDIDATE_OUT_DIR", str(out_dir))
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate", "--network-mode=no_network"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    report = out_dir / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"
    data = json.loads(report.read_text())
    assert data["broker_contact_during_validation"] is False
