"""Task I validation script: run all milestone checks and write proof bundles."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv(Path(__file__).parent.parent / ".env")

from core.ontology import AccountMode
from dashboard.backend.main import app
from proof.ledger import list_proofs, write_proof

ROOT = Path(__file__).parent.parent
BLUNDER_ROOT = Path("C:/src/engine/obtuse/blunder")
DUMBY_BLUNDER = ROOT / "core" / "inherited_blunder"
DASHBOARD_DIST = ROOT / "dashboard" / "frontend" / "dist"
LOG_FILE = ROOT / "logs" / "dumby.jsonl"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _source_manifest(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): sha256_file(p)
        for p in root.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and "__pycache__" not in p.parts
        and p.name != ".blunder_source_manifest.json"
    }


def validate_blunder_copy() -> tuple[str, dict]:
    if not BLUNDER_ROOT.exists():
        return "FAIL", {"error": f"Canonical Blunder root missing: {BLUNDER_ROOT}"}
    if not DUMBY_BLUNDER.exists():
        return "FAIL", {"error": f"Inherited Blunder root missing: {DUMBY_BLUNDER}"}
    manifest_path = DUMBY_BLUNDER / ".blunder_source_manifest.json"
    if not manifest_path.exists():
        return "FAIL", {"error": "Inherited Blunder manifest missing"}
    copied_manifest = json.loads(manifest_path.read_text())
    source_manifest = _source_manifest(BLUNDER_ROOT)
    if source_manifest != copied_manifest:
        only_source = set(source_manifest) - set(copied_manifest)
        only_copied = set(copied_manifest) - set(source_manifest)
        mismatched = {k for k in (set(source_manifest) & set(copied_manifest)) if source_manifest[k] != copied_manifest[k]}
        return "FAIL", {
            "source_files": len(source_manifest),
            "copied_files": len(copied_manifest),
            "only_in_source": sorted(only_source),
            "only_in_copied": sorted(only_copied),
            "hash_mismatches": sorted(mismatched),
        }
    return "PASS", {
        "source_files": len(source_manifest),
        "copied_files": len(copied_manifest),
        "manifest_matches": True,
    }


def validate_dashboard() -> tuple[str, dict]:
    if not DASHBOARD_DIST.exists():
        return "FAIL", {"built": False, "error": "dist/ missing"}
    index_html = DASHBOARD_DIST / "index.html"
    assets = list((DASHBOARD_DIST / "assets").glob("*")) if (DASHBOARD_DIST / "assets").exists() else []
    if not index_html.exists():
        return "FAIL", {"built": False, "has_index_html": False, "assets_count": len(assets)}
    return "PASS", {"built": True, "has_index_html": True, "assets_count": len(assets)}


def validate_backend() -> tuple[str, dict]:
    endpoints = [
        "/status", "/markets", "/forecasts", "/strategies", "/orders",
        "/positions", "/risk", "/proof", "/logs", "/repo-harvester/status",
        "/repo-harvester/repos", "/repo-harvester/reports",
    ]
    results = []
    try:
        with TestClient(app) as client:
            for ep in endpoints:
                r = client.get(ep)
                results.append({"endpoint": ep, "status": r.status_code})
            with client.websocket_connect("/ws/status") as ws:
                data = ws.receive_json()
                ws_ok = "mode" in data
    except Exception as e:
        return "FAIL", {"endpoints": results, "websocket_ok": False, "error": str(e)}
    all_ok = all(r["status"] == 200 for r in results) and ws_ok
    return ("PASS" if all_ok else "FAIL"), {"endpoints": results, "websocket_ok": ws_ok}


def _run_pytest(test_path: str) -> dict:
    cmd = [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    passed = proc.returncode == 0
    summary_match = re.search(r"(\d+) passed(?:, (\d+) failed)?", proc.stdout)
    total_match = re.search(r"collected (\d+) item", proc.stdout)
    return {
        "passed": passed,
        "returncode": proc.returncode,
        "total": int(total_match.group(1)) if total_match else None,
        "passed_count": int(summary_match.group(1)) if summary_match else None,
        "failed_count": int(summary_match.group(2)) if summary_match and summary_match.group(2) else 0,
    }


def validate_kalshi() -> tuple[str, dict]:
    off = _run_pytest("tests/test_live_firewall.py::test_off_mode_blocks_orders")
    read_only = _run_pytest("tests/test_live_firewall.py::test_read_only_blocks_orders")
    autonomous = _run_pytest("tests/test_live_firewall.py::test_all_gates_pass_allows")
    client_smoke = _run_pytest("tests/test_kalshi_client.py::test_get_orderbook_parsing")
    all_pass = all(r["passed"] for r in (off, read_only, autonomous, client_smoke))
    payload = {
        "off_mode_blocks": off,
        "read_only_blocks": read_only,
        "autonomous_routes": autonomous,
        "kalshi_client_smoke": client_smoke,
        "referenced_tests": [
            "tests/test_live_firewall.py::test_off_mode_blocks_orders",
            "tests/test_live_firewall.py::test_read_only_blocks_orders",
            "tests/test_live_firewall.py::test_all_gates_pass_allows",
            "tests/test_kalshi_client.py::test_get_orderbook_parsing",
        ],
    }
    return ("PASS" if all_pass else "FAIL"), payload


def validate_secret_redaction() -> tuple[str, dict]:
    secret = os.environ.get("KALSHI_API_KEY_ID", "")
    leaks = []
    # Scan logs
    if LOG_FILE.exists() and secret:
        for line in LOG_FILE.read_text().splitlines():
            if secret in line:
                leaks.append({"source": str(LOG_FILE), "snippet": line[:200]})
    # Scan proof bundles
    for proof_path in (ROOT / "proof").glob("*.json"):
        text = proof_path.read_text()
        if secret and secret in text:
            leaks.append({"source": str(proof_path), "snippet": "KALSHI_API_KEY_ID value found"})
    return ("PASS" if not leaks else "FAIL"), {"secret_configured": bool(secret), "leaks": leaks}


def validate_no_paper_ladder() -> tuple[str, dict]:
    modes = [m.value for m in AccountMode]
    has_paper = any("PAPER" in m for m in modes)
    return ("PASS" if not has_paper else "FAIL"), {"modes": modes, "paper_found": has_paper}


def main():
    checks = {
        "blunder_copy": validate_blunder_copy,
        "dashboard": validate_dashboard,
        "backend": validate_backend,
        "kalshi": validate_kalshi,
        "secret_redaction": validate_secret_redaction,
        "no_paper_ladder": validate_no_paper_ladder,
    }
    summary = {}
    all_pass = True
    for component, fn in checks.items():
        verdict, payload = fn()
        ref_id = write_proof(component, verdict, payload)
        summary[component] = {"verdict": verdict, "ref_id": ref_id, "payload": payload}
        if verdict != "PASS":
            all_pass = False
    summary["overall"] = "PASS" if all_pass else "FAIL"
    summary["proof_bundles"] = list_proofs()
    print(json.dumps(summary, indent=2, default=str))
    return summary


if __name__ == "__main__":
    main()
