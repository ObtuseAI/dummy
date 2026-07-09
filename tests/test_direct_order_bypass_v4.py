"""Static scan proving only allowed files call create_order."""

import re
from pathlib import Path

ALLOWED_CREATE_ORDER_FILES = {
    "live_firewall/firewall.py",
    "kalshi/submitter.py",
}


def _source_has_create_order_call(source: str) -> bool:
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    for line in source.splitlines():
        if call_re.search(line) and "def create_order(" not in line:
            return True
    return False


def test_only_allowed_files_call_create_order():
    """Only the firewall and the submitter helper may invoke create_order."""
    offenders = []
    excluded = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "tests"}
    for py in Path(".").rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        try:
            source = py.read_text(encoding="utf-8")
        except Exception:
            continue
        if _source_has_create_order_call(source):
            rel = py.relative_to(Path(".")).as_posix()
            if rel not in ALLOWED_CREATE_ORDER_FILES:
                offenders.append(rel)
    assert not offenders, f"Unexpected create_order callers: {offenders}"
