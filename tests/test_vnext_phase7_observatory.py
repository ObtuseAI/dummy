from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

def test_phase7_audit_is_byte_deterministic_and_honest(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_vnext_phase7_audit.py"
    command = [sys.executable, str(script), "--output-dir", str(tmp_path)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    first = {path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))}
    subprocess.run(command, check=True, capture_output=True, text=True)
    second = {path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))}
    assert first == second
    arena = json.loads(first["VNEXT_PHASE7_ARENA_REPRODUCIBILITY.json"])
    snapshot = json.loads(first["VNEXT_PHASE7_OBSERVATORY_SNAPSHOT.json"])
    assert arena["status"] == "MECHANICS_VALIDATED_NO_EMPIRICAL_CLAIM"
    assert arena["runtime_episode_count"] == 0
    assert snapshot["telemetry_status"] == "POINT_IN_TIME_SNAPSHOT_NO_LIVE_TELEMETRY"
