"""V2 model-proof order path tests."""

import re
from pathlib import Path


ROOT = Path("C:/src/engine/dummy")


def _has_create_order_call(source: str) -> bool:
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    for line in source.splitlines():
        if call_re.search(line) and "def create_order(" not in line:
            return True
    return False


def test_only_allowed_callers_invoke_create_order():
    excluded = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "tests",
        "artifacts",
    }
    offenders = set()
    for py in ROOT.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        if _has_create_order_call(text):
            offenders.add(py.relative_to(ROOT).as_posix())

    allowed = {"live_firewall/firewall.py", "kalshi/submitter.py"}
    assert offenders <= allowed, offenders


def test_v2_rehearsal_uses_proof_ledger():
    hybrid_path = ROOT / "execution" / "hybrid_path.py"
    source = hybrid_path.read_text(encoding="utf-8", errors="ignore")
    assert "class HybridLiveCapRehearsalV2" in source
    assert "write_proof" in source
    assert "opinion.proof_reference" in source
    assert "proposal.proof_reference" in source


def test_v2_rehearsal_has_no_direct_create_order_call():
    hybrid_path = ROOT / "execution" / "hybrid_path.py"
    source = hybrid_path.read_text(encoding="utf-8", errors="ignore")
    assert not _has_create_order_call(source)
