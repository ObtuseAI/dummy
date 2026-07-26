"""The autonomy executor and central firewall are the only live order route."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _has_create_order_call(source: str) -> bool:
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    return any(
        call_re.search(line) and "def create_order(" not in line
        for line in source.splitlines()
    )


def test_only_central_transport_modules_invoke_create_order():
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
    offenders = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.py")
        if not any(part in excluded for part in path.parts)
        and _has_create_order_call(
            path.read_text(encoding="utf-8", errors="ignore")
        )
    }
    assert offenders <= {
        "live_firewall/firewall.py",
        "kalshi/submitter.py",
    }, offenders


def test_legacy_execution_paths_are_removed_and_canonical_path_is_attested():
    assert not (ROOT / "execution" / "autonomous_path.py").exists()
    assert not (ROOT / "execution" / "hybrid_path.py").exists()
    source = (ROOT / "autonomy" / "executor.py").read_text(encoding="utf-8")
    assert "firewall.submit(request, orderbook, firewall_forecast)" in source
    assert "model_influence_attestation=build_model_influence_attestation(" in source
