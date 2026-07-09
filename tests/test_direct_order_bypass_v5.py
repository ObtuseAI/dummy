from pathlib import Path
import re

ROOT = Path(__file__).parent.parent


def test_only_firewall_and_submitter_call_create_order():
    allowed = {"live_firewall/firewall.py", "kalshi/submitter.py"}
    offenders = []
    excluded = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "tests"}
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    for py in ROOT.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        try:
            source = py.read_text(encoding="utf-8")
        except Exception:
            continue
        for line in source.splitlines():
            if call_re.search(line) and "def create_order(" not in line:
                rel = py.relative_to(ROOT).as_posix()
                if rel not in allowed:
                    offenders.append(rel)
                break
    assert not offenders, f"unexpected create_order callers: {offenders}"
