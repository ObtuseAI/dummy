import json
from datetime import datetime, timezone
from pathlib import Path
from core.state import STATE
from core.config_loader import load_caps

ARTIFACTS = Path("C:/src/engine/dumby/artifacts/dumby")
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def _write(name: str, payload: dict):
    (ARTIFACTS / name).write_text(json.dumps(payload, indent=2, default=str))


def generate_reports(**kwargs):
    now = datetime.now(timezone.utc).isoformat()
    _write("final_report.json", {"status": kwargs.get("status", "PARTIAL"), "generated_at": now, "summary": kwargs.get("summary", "")})
    _write("tests_summary.json", kwargs.get("tests_summary", {"total": 0, "passed": 0, "failed": 0}))
    _write("full_blunder_copy_report.json", kwargs.get("blunder_report", {"status": "PENDING"}))
    _write("dashboard_report.json", kwargs.get("dashboard_report", {"built": False}))
    _write("backend_api_report.json", kwargs.get("backend_report", {"endpoints": []}))
    _write("kalshi_adapter_report.json", kwargs.get("kalshi_report", {"status": "PENDING"}))
    _write("live_firewall_report.json", kwargs.get("firewall_report", {"status": "PENDING"}))
    _write("risk_governor_report.json", kwargs.get("risk_report", {"status": "PENDING"}))
    _write("compliance_governor_report.json", kwargs.get("compliance_report", {"status": "PENDING"}))
    _write("repo_harvester_report.json", kwargs.get("repo_harvester_report", {"status": "PENDING"}))
    _write("repo_manifest.json", kwargs.get("repo_manifest", {"repos": []}))
    _write("repo_classification_report.json", kwargs.get("repo_classification", {"classes": []}))
    _write("no_secret_leak_report.json", kwargs.get("secret_report", {"leaks": []}))
    _write("no_paper_ladder_report.json", {"paper_ladder_required": False})
    _write("proof_bundle_manifest.json", kwargs.get("proof_manifest", {"bundles": []}))
