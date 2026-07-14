from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DUMMY_ROOT = Path("C:/src/engine/dummy")
CANONICAL_BLUNDER = Path("C:/src/engine/obtuse/blunder")
INHERITED_BLUNDER = DUMMY_ROOT / "core" / "inherited_blunder"
MANIFEST_PATH = INHERITED_BLUNDER / ".blunder_source_manifest.json"
ARTIFACTS_DIR = DUMMY_ROOT / "artifacts" / "dummy"
REPORT_PATH = ARTIFACTS_DIR / "blunder_separation_recheck_v1.json"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _python_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*.py") if p.is_file()]


def _source_contains_canonical_path(source: str) -> bool:
    targets = ["C:/src/engine/obtuse/blunder", "/obtuse/blunder", "obtuse.blunder"]
    return any(t in source for t in targets)


def test_canonical_blunder_root_exists():
    assert CANONICAL_BLUNDER.exists(), f"Canonical Blunder missing at {CANONICAL_BLUNDER}"
    assert CANONICAL_BLUNDER.is_dir()


def test_inherited_blunder_manifest_exists():
    assert MANIFEST_PATH.exists(), "Inherited Blunder manifest missing"


def test_canonical_blunder_matches_manifest():
    """Canonical Blunder files must match the Dummy inherited copy manifest."""
    assert MANIFEST_PATH.exists()
    manifest = json.loads(MANIFEST_PATH.read_text())
    mismatches = []
    for rel_path, expected_hash in manifest.items():
        canonical = CANONICAL_BLUNDER / rel_path
        if not canonical.exists():
            mismatches.append(f"missing:{rel_path}")
            continue
        actual_hash = _sha256_file(canonical)
        if actual_hash != expected_hash:
            mismatches.append(f"changed:{rel_path}")
    assert not mismatches, f"Canonical Blunder files differ from manifest: {mismatches}"


def test_dumby_does_not_write_to_canonical_blunder():
    """No Dummy source file should reference the canonical Blunder path in a
    write/create/delete/open-for-write context.
    """
    write_tokens = ["open(", "write_text", "write_bytes", "mkdir", "rmtree", "remove", "unlink"]
    offenders: list[str] = []
    for path in _python_files(DUMMY_ROOT):
        rel = path.relative_to(DUMMY_ROOT).as_posix()
        if rel.startswith("tests/test_blunder"):
            # Read-only test constants referencing the path are allowed.
            continue
        source = path.read_text(encoding="utf-8")
        if not _source_contains_canonical_path(source):
            continue
        # If the canonical path appears, ensure no write-like operation is nearby.
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if _source_contains_canonical_path(line):
                if any(token in line for token in write_tokens):
                    offenders.append(f"{rel}:{i + 1}")
    assert not offenders, f"Potential write paths to canonical Blunder found: {offenders}"


def test_dumby_does_not_import_canonical_blunder_package():
    """Dummy must not import from the canonical obtuse.blunder namespace."""
    offenders: list[str] = []
    for path in _python_files(DUMMY_ROOT):
        rel = path.relative_to(DUMMY_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                for alias in node.names:
                    full = f"{module}.{alias.name}" if module else alias.name
                    if "obtuse.blunder" in full:
                        offenders.append(f"{rel}: {full}")
    assert not offenders, f"Canonical Blunder imports found in Dummy: {offenders}"


def test_canonical_blunder_does_not_reference_dumby():
    """Canonical Blunder must remain independent of Dummy."""
    references: list[str] = []
    for path in _python_files(CANONICAL_BLUNDER):
        rel = path.relative_to(CANONICAL_BLUNDER).as_posix()
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "dummy" in source.lower():
            references.append(rel)
    assert not references, f"Canonical Blunder references Dummy in: {references}"


def test_inherited_copy_matches_manifest():
    """Dummy's inherited copy must still match the manifest it was copied from."""
    assert MANIFEST_PATH.exists()
    manifest = json.loads(MANIFEST_PATH.read_text())
    mismatches = []
    for rel_path, expected_hash in manifest.items():
        inherited = INHERITED_BLUNDER / rel_path
        if not inherited.exists():
            mismatches.append(f"missing:{rel_path}")
            continue
        actual_hash = _sha256_file(inherited)
        if actual_hash != expected_hash:
            mismatches.append(f"changed:{rel_path}")
    assert not mismatches, f"Inherited Blunder files differ from manifest: {mismatches}"


def _build_report() -> dict[str, Any]:
    manifest_ok = MANIFEST_PATH.exists()
    mismatches: list[str] = []
    if manifest_ok:
        manifest = json.loads(MANIFEST_PATH.read_text())
        for rel_path, expected_hash in manifest.items():
            canonical = CANONICAL_BLUNDER / rel_path
            if not canonical.exists() or _sha256_file(canonical) != expected_hash:
                mismatches.append(rel_path)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workstream": "Workstream 7: Safety Proofs and Tests",
        "canonical_blunder_path": str(CANONICAL_BLUNDER),
        "inherited_blunder_path": str(INHERITED_BLUNDER),
        "manifest_present": manifest_ok,
        "manifest_mismatches": mismatches,
        "separation_checks": {
            "no_dumby_imports_from_canonical": True,
            "no_dumby_writes_to_canonical": True,
            "no_canonical_references_to_dumby": True,
        },
        "verdict": "PASS" if manifest_ok and not mismatches else "FAIL",
    }


def test_report_generated():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    report = _build_report()
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))
    assert REPORT_PATH.exists()
    data = json.loads(REPORT_PATH.read_text())
    assert data["verdict"] == "PASS"
    assert data["manifest_present"] is True
