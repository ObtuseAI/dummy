import re
from pathlib import Path


def test_only_allowed_callers_invoke_create_order():
    root = Path("C:/src/engine/dummy")
    excluded = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "tests", "artifacts"}
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    offenders = set()
    for py in root.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if call_re.search(line) and "def create_order(" not in line:
                offenders.add(py.relative_to(root).as_posix())
                break
    allowed = {"live_firewall/firewall.py", "kalshi/submitter.py"}
    assert offenders <= allowed, offenders
