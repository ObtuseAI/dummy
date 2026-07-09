import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests._real_proof_test_helpers import make_evidence_bundle, patch_artifact_paths

CLI = [sys.executable, "-m", "tools.operator_authority_appliance.operator_full_completion"]


def test_candidate_validation_does_not_unlock_submit(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path, broker_rejected=True)
    patch_artifact_paths(monkeypatch, tmp_path)
    out_dir = tmp_path / "next_proof_candidate"
    monkeypatch.setenv("DUMMY_NEXT_PROOF_CANDIDATE_OUT_DIR", str(out_dir))
    result = subprocess.run(
        [*CLI, "validate-next-proof-candidate", "--network-mode=mock"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    candidate_path = out_dir / "VALIDATED_KALSHI_PROOF_CANDIDATE.json"
    candidate = json.loads(candidate_path.read_text())
    assert candidate["submit_allowed_now"] is False
    assert candidate["requires_new_operator_proof_authority"] is True
    assert candidate["proof_lock_status"] == "consumed_by_real_broker_attempt"


def test_one_shot_check_still_blocked_after_candidate_validation(tmp_path, monkeypatch):
    bundle = make_evidence_bundle(tmp_path, broker_rejected=True)
    patch_artifact_paths(monkeypatch, tmp_path)
    subprocess.run([*CLI, "validate-next-proof-candidate"], capture_output=True, cwd=tmp_path)
    result = subprocess.run([*CLI, "one-shot-check"], capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode != 0 or "BLOCKED" in result.stdout or "BLOCKED" in result.stderr
