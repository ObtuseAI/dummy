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


def test_autoresearch_audit_projects_real_level_zero_campaign() -> None:
    campaign = {
        "campaign_id": "campaign-1",
        "scope": "crypto|btc|15m_direction|15m",
        "genuine_private_candidate_trials": 5,
        "genuine_external_generalization_trials": 0,
        "private_survivors": 0,
        "external_survivors": 0,
        "candidates": [],
    }
    forward = {
        "status": "ACCUMULATING_FORWARD_EVIDENCE",
        "forward_paper_candidate_settlements": 0,
        "performance_claim_supported": False,
    }
    ignition = {
        "highest_supported_recursive_improvement_level": 0,
        "self_improvement_claim_supported": False,
        "improved_improver_claim_supported": False,
        "accelerating_improvement_claim_supported": False,
    }
    outputs = build_outputs(campaign, forward, ignition)
    evidence = outputs["VNEXT_AUTORESEARCH_EVIDENCE.json"]
    assert evidence["genuine_private_candidate_trials"] == 5
    assert evidence["highest_supported_recursive_improvement_level"] == 0
    assert evidence["status"] == (
        "LEVEL0_AUTONOMOUS_EXPERIMENTATION_LEVEL1_NOT_SUPPORTED"
    )
    assert evidence["self_improvement_claim_supported"] is False
    assert "VNEXT_AUTORESEARCH_CAMPAIGN.json" in outputs
    assert "VNEXT_AUTORESEARCH_FORWARD_EVIDENCE.json" in outputs
    assert "VNEXT_AUTORESEARCH_IGNITION.json" in outputs
