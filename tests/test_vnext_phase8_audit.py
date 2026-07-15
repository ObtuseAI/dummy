from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_phase8_audit_is_byte_deterministic_and_fail_closed(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_vnext_phase8_audit.py"
    command = [sys.executable, str(script), "--output-dir", str(tmp_path)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    first = {path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))}
    subprocess.run(command, check=True, capture_output=True, text=True)
    second = {path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))}
    assert first == second

    catalog = json.loads(first["VNEXT_PHASE8_BENCHMARK_CATALOG.json"])
    governance = json.loads(first["VNEXT_PHASE8_GOVERNANCE_EVIDENCE.json"])
    claims = json.loads(first["VNEXT_PHASE8_CLAIM_REVIEW.json"])
    promotion = json.loads(first["VNEXT_PHASE8_PROMOTION_REVIEW.json"])
    assert catalog["metric_count"] == 32
    assert all(governance["checks"].values())
    assert governance["candidate_controls_audit"] is False
    assert claims["performance_supported_count"] == 0
    assert claims["governance_supported_count"] == 2
    assert claims["insufficient_evidence_count"] == 6
    assert claims["material_improvement_established"] is False
    assert promotion["transition_eligible"] is False
    assert promotion["human_review_required"] is True
    assert promotion["automatic_promotion"] is False
    assert promotion["applied"] is False
