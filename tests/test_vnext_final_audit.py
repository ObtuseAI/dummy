from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.run_vnext_final_audit import build_audit


def test_final_audit_covers_every_master_plan_section_honestly() -> None:
    audit = build_audit()
    assert audit["status"] == "PASS_WITH_EMPIRICAL_GATES_OPEN"
    assert audit["repository_identity"] == "DUMMY_STANDALONE"
    assert audit["requirement_count"] == 38
    assert [item["section"] for item in audit["requirements"]] == list(range(1, 39))
    assert audit["requirements_with_missing_paths"] == 0
    assert all(not item["missing_paths"] for item in audit["requirements"])
    assert audit["first_complete_capability"]["step_count"] == 20
    assert audit["first_complete_capability"]["mechanically_validated"] is True
    assert audit["claim_program"]["performance_supported_count"] == 0
    assert audit["claim_program"]["governance_supported_count"] == 2
    assert audit["claim_program"]["insufficient_evidence_count"] == 6
    assert audit["claim_program"]["material_improvement_established"] is False
    assert audit["promotion"]["transition_eligible"] is False
    assert audit["promotion"]["automatic_promotion"] is False
    assert audit["promotion"]["applied"] is False
    assert audit["governance"]["dummy_is_standalone_entity"] is True
    assert audit["governance"]["legacy_snapshot_is_identity"] is False
    assert audit["validation"]["evidence_mode"] == "SOURCE_CONTRACT_ONLY"
    assert audit["validation"]["current_test_run_required"] is True
    assert audit["validation"]["archived_frontend_required"] is False


def test_final_audit_command_is_byte_deterministic(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_vnext_final_audit.py"
    output = tmp_path / "audit.json"
    command = [sys.executable, str(script), "--output", str(output)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    first = output.read_bytes()
    subprocess.run(command, check=True, capture_output=True, text=True)
    assert output.read_bytes() == first
    assert json.loads(first)["status"] == "PASS_WITH_EMPIRICAL_GATES_OPEN"
