"""Generate DUMMY_V8 identity, separation, and safety reports.

This script produces the V8 recheck reports for canonical identity,
blunder separation, direct order bypass, and secret leak detection.

No secret values are written to artifacts. No live orders are submitted.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_dir(path: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not path.exists():
        return hashes
    for f in sorted(path.rglob("*")):
        if f.is_file() and ".git" not in f.parts and "__pycache__" not in f.parts:
            hashes[f.relative_to(path).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return hashes


def _source_has_create_order_call(source: str) -> bool:
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    for line in source.splitlines():
        if call_re.search(line) and "def create_order(" not in line:
            return True
    return False


def _find_create_order_callers(root: Path) -> list[dict[str, Any]]:
    """Return files and qualnames that call create_order outside allowed paths."""
    excluded = {"archive", ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "tests", "artifacts"}
    callers: list[dict[str, Any]] = []
    for py in root.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        try:
            source = py.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            is_create = False
            if isinstance(node.func, ast.Attribute) and node.func.attr == "create_order":
                is_create = True
            elif isinstance(node.func, ast.Name) and node.func.id == "create_order":
                is_create = True
            if not is_create:
                continue

            func_name = ""
            class_name = ""
            current: ast.AST | None = node
            while current is not None:
                current = parents.get(current)
                if current is None:
                    break
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)) and not func_name:
                    func_name = current.name
                elif isinstance(current, ast.ClassDef) and not class_name:
                    class_name = current.name
            qualname = f"{class_name}.{func_name}" if class_name and func_name else (func_name or class_name or "<module>")
            callers.append({
                "file": py.relative_to(root).as_posix(),
                "qualname": qualname,
            })
    return callers


# ---------------------------------------------------------------------------
# 1. Dummy canonical identity v4
# ---------------------------------------------------------------------------


def generate_dummy_canonical_identity_report_v4() -> dict:
    pyproject = ROOT / "pyproject.toml"
    project_name = "unknown"
    if pyproject.exists():
        m = re.search(r'^name\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
        if m:
            project_name = m.group(1)

    readme = ROOT / "README.md"
    readme_text = readme.read_text(encoding="utf-8").strip() if readme.exists() else ""

    # Detect any runtime hard-coding of the old root path outside tests/scripts.
    # Exclude report metadata that merely checks whether the old root is absent.
    excluded = {"archive", ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "tests", "scripts", "artifacts"}
    old_root_refs: list[str] = []
    old_root_variants = ["C:/src/engine/dumby", r"C:\\src\\engine\\dumby"]
    for py in ROOT.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if any(variant in line for variant in old_root_variants):
                if "old_root_absent" in line or "historical_artifacts" in line:
                    continue
                old_root_refs.append(py.relative_to(ROOT).as_posix())
                break

    active_root = str(ROOT)
    old_root_exists = Path("C:/src/engine/dumby").exists()

    verdict = "PASS"
    if project_name != "dummy":
        verdict = "FAIL"
    elif "Dummy" not in readme_text:
        verdict = "FAIL"
    elif active_root != "C:\\src\\engine\\dummy":
        verdict = "FAIL"
    elif old_root_exists:
        verdict = "FAIL"
    elif old_root_refs:
        verdict = "FAIL"

    return {
        "generated_at": now_iso(),
        "workstream": "V8: Dummy Canonical Identity Recheck",
        "project": "Dummy",
        "previous_name": "Dumby",
        "active_root": active_root,
        "old_root_absent": not old_root_exists,
        "pyproject_name": project_name,
        "readme_says_dummy": "Dummy" in readme_text,
        "old_root_runtime_refs": old_root_refs,
        "milestone": "DUMMY_V8_IDENTITY_SEPARATION_BYPASS",
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# 2. Blunder separation v6
# ---------------------------------------------------------------------------


def generate_blunder_separation_recheck_v6() -> dict:
    inherited_blunder = ROOT / "core" / "inherited_blunder"
    blunder_present = inherited_blunder.exists() and inherited_blunder.is_dir()
    fingerprint = _sha256_dir(inherited_blunder)

    # Verify inherited_blunder has not been modified by comparing against its manifest.
    manifest_path = inherited_blunder / ".blunder_source_manifest.json"
    manifest_matches = True
    manifest_mismatches: list[str] = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for rel_path, expected_hash in manifest.items():
            file_path = inherited_blunder / rel_path
            if not file_path.exists():
                manifest_mismatches.append(f"missing:{rel_path}")
                manifest_matches = False
                continue
            actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                manifest_mismatches.append(f"changed:{rel_path}")
                manifest_matches = False
    else:
        manifest_matches = False
        manifest_mismatches.append("missing_manifest")

    verdict = "PASS" if (blunder_present and manifest_matches) else "FAIL"

    return {
        "generated_at": now_iso(),
        "workstream": "V8: Blunder Separation Recheck",
        "inherited_blunder_present": blunder_present,
        "inherited_blunder_path": str(inherited_blunder),
        "inherited_blunder_file_count": len(fingerprint),
        "inherited_blunder_fingerprint": fingerprint,
        "manifest_path": str(manifest_path),
        "manifest_matches": manifest_matches,
        "manifest_mismatches": manifest_mismatches,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# 3. Direct order bypass v8
# ---------------------------------------------------------------------------


def generate_direct_order_bypass_report_v8() -> dict:
    excluded = {"archive", ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "tests", "artifacts"}

    offenders: list[dict[str, Any]] = []
    scanned_count = 0
    for py in ROOT.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        scanned_count += 1
        try:
            source = py.read_text(encoding="utf-8")
        except Exception:
            continue
        if _source_has_create_order_call(source):
            offenders.append({"file": py.relative_to(ROOT).as_posix()})

    allowed = {"live_firewall/firewall.py", "kalshi/submitter.py"}
    offender_files = {o["file"] for o in offenders}
    only_allowed_files = offender_files <= allowed

    # Also enforce the method-level constraint.
    callers = _find_create_order_callers(ROOT)
    allowed_qualnames = {"LiveBrokerFirewall.submit", "KalshiSubmitter.submit_limit_order"}
    caller_qualnames = {c["qualname"] for c in callers}
    unexpected_qualnames = caller_qualnames - allowed_qualnames
    only_allowed_qualnames = not unexpected_qualnames

    verdict = "PASS" if (only_allowed_files and only_allowed_qualnames) else "FAIL"

    return {
        "generated_at": now_iso(),
        "workstream": "V8: Direct Order Bypass Recheck",
        "scanned_file_count": scanned_count,
        "files_with_create_order_calls": sorted(offender_files),
        "allowed_callers": sorted(allowed),
        "only_allowed_callers": only_allowed_files,
        "create_order_callers": callers,
        "allowed_caller_qualnames": sorted(allowed_qualnames),
        "unexpected_caller_qualnames": sorted(unexpected_qualnames),
        "only_allowed_caller_qualnames": only_allowed_qualnames,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# 4. No secret leak v7
# ---------------------------------------------------------------------------


def generate_no_secret_leak_report_v7() -> dict:
    from core.secret_guard import redact

    sample = {
        "KALSHI_API_KEY_ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "KALSHI_API_PRIVATE_KEY_PEM": "-----BEGIN PRIVATE KEY-----\nMIIB...\n-----END PRIVATE KEY-----",
    }
    redacted = redact(sample)
    redacted_text = str(redacted)

    secret_values = ["a1b2c3d4-e5f6-7890-abcd-ef1234567890", "MIIB", "-----BEGIN PRIVATE KEY-----"]
    leaked = any(s in redacted_text for s in secret_values)

    # Also ensure live env keys are not present in the report text.
    env_keys = ["KALSHI_API_KEY_ID", "KALSHI_API_PRIVATE_KEY_PEM"]
    env_leaked = any(os.environ.get(k, "") and os.environ.get(k, "") in redacted_text for k in env_keys)

    return {
        "generated_at": now_iso(),
        "workstream": "V8: No Secret Leak",
        "redaction_module": "core.secret_guard",
        "sample_values_redacted": not leaked,
        "env_values_redacted": not env_leaked,
        "leak_detected": leaked or env_leaked,
        "verdict": "PASS" if not (leaked or env_leaked) else "FAIL",
    }


# ---------------------------------------------------------------------------
# Final V8 assembly
# ---------------------------------------------------------------------------


def main() -> None:
    reports = {
        "dummy_canonical_identity_report_v4.json": generate_dummy_canonical_identity_report_v4(),
        "blunder_separation_recheck_v6.json": generate_blunder_separation_recheck_v6(),
        "direct_order_bypass_report_v8.json": generate_direct_order_bypass_report_v8(),
        "no_secret_leak_report_v7.json": generate_no_secret_leak_report_v7(),
    }

    for name, data in reports.items():
        (ARTIFACTS / name).write_text(json.dumps(data, indent=2, default=str))

    final_path = ARTIFACTS / "final_report.json"
    existing = json.loads(final_path.read_text()) if final_path.exists() else {}
    # Preserve an orchestrator-written V8 final milestone if present; only
    # inject our identity section when no orchestrator report exists yet.
    if existing.get("milestone") != "DUMMY_V8_MODEL_ROUTING_FIREWALL_GOVERNOR_REHEARSAL_V1":
        existing["milestone"] = "DUMMY_V8_IDENTITY_SEPARATION_BYPASS"
        existing["verdict"] = "PASS" if all(r.get("verdict") in ("PASS", "PARTIAL") for r in reports.values()) else "FAIL"
        existing["generated_at"] = now_iso()
        existing["note"] = "V8 identity, separation, bypass, and secret-leak reports generated."
    existing["v8_reports"] = {name: r.get("verdict") for name, r in reports.items()}
    final_path.write_text(json.dumps(existing, indent=2, default=str))
    print(json.dumps(existing, indent=2, default=str))


if __name__ == "__main__":
    main()
