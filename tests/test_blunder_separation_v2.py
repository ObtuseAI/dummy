"""Verify Dummy does not import from or modify canonical Blunder."""

import subprocess
from pathlib import Path

BLUNDER_ROOT = Path("C:/src/engine/obtuse/blunder")


def test_dumby_does_not_import_blunder():
    """No Dummy Python file imports the canonical Blunder package."""
    excluded = {"archive", ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "tests", "scripts"}
    for py in Path(".").rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        assert "obtuse.blunder" not in text, f"{py} references canonical Blunder"


def test_blunder_unchanged():
    """Canonical Blunder working tree has no uncommitted changes."""
    if not BLUNDER_ROOT.exists():
        return
    result = subprocess.run(
        ["git", "-C", str(BLUNDER_ROOT), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    assert not result.stdout.strip(), "Canonical Blunder has uncommitted changes"
