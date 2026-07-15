from __future__ import annotations

import json
import re
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
    assert audit["validation"]["cross_vnext_tests"] == 197
    assert audit["validation"]["repository_tests"] == 5696
    assert audit["validation"]["dashboard_entry_bundle_kb"] == 302.00
    assert audit["validation"]["oversized_chunk_warning"] is False


def test_final_audit_command_is_byte_deterministic(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_vnext_final_audit.py"
    output = tmp_path / "audit.json"
    command = [sys.executable, str(script), "--output", str(output)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    first = output.read_bytes()
    subprocess.run(command, check=True, capture_output=True, text=True)
    assert output.read_bytes() == first
    assert json.loads(first)["status"] == "PASS_WITH_EMPIRICAL_GATES_OPEN"


def test_all_archived_dashboard_routes_are_lazy_and_preserved() -> None:
    source_root = Path("dashboard/frontend/src")
    app = (source_root / "App.jsx").read_text(encoding="utf-8")
    lazy_route = (source_root / "LegacyDashboardRoute.jsx").read_text(
        encoding="utf-8"
    )
    dashboard_versions = {
        match.group(1)
        for path in source_root.glob("V*Dashboard.jsx")
        if (match := re.fullmatch(r"V(\d+)Dashboard\.jsx", path.name))
    }
    route_versions = set(
        re.findall(
            r'path="/v(\d+)-dashboard" '
            r"element={<LegacyDashboardRoute version={(\d+)} />}",
            app,
        )
    )
    assert len(dashboard_versions) == 293
    assert route_versions == {(version, version) for version in dashboard_versions}
    assert not re.search(r"^import V\d+Dashboard from './V\d+Dashboard';", app, re.M)
    assert "import.meta.glob('./V*Dashboard.jsx')" in lazy_route
    assert "lazy(loader)" in lazy_route
