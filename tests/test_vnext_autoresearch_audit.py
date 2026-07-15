from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.run_vnext_autoresearch_audit import build_outputs


def test_autoresearch_audit_is_deterministic_and_honest() -> None:
    first = build_outputs()
    second = build_outputs()
    assert first == second
    policy = first["VNEXT_AUTORESEARCH_POLICY.json"]
    evidence = first["VNEXT_AUTORESEARCH_EVIDENCE.json"]
    assert policy["execution_authority"] is False
    assert policy["automatic_promotion"] is False
    assert evidence["mechanics_implemented"] is True
    assert evidence["genuine_private_candidate_trials"] == 0
    assert evidence["performance_claim_supported"] is False
    assert evidence["highest_supported_recursive_improvement_level"] is None


def test_autoresearch_audit_cli_writes_expected_artifacts(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_vnext_autoresearch_audit.py"
    result = subprocess.run(
        [sys.executable, str(script), "--output-dir", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout)
    assert summary["empirical_recursive_improvement_claim"] is False
    assert (tmp_path / "VNEXT_AUTORESEARCH_POLICY.json").exists()
    assert (tmp_path / "VNEXT_AUTORESEARCH_EVIDENCE.json").exists()
