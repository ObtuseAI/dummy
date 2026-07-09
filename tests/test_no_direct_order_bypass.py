from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

DUMMY_ROOT = Path("C:/src/engine/dummy")
ADAPTERS_DIR = DUMMY_ROOT / "adapters" / "promoted"
STRATEGIES_DIR = DUMMY_ROOT / "strategies" / "repo_derived"
ARTIFACTS_DIR = DUMMY_ROOT / "artifacts" / "dummy"
REPORT_PATH = ARTIFACTS_DIR / "no_direct_order_bypass_report_v1.json"

FORBIDDEN_CALLS = {
    "create_order",
    "cancel_order",
    "submit_order",
    "market_order",
    "delete_order",
    "place_order",
}
FORBIDDEN_IMPORTS = {
    "kalshi.client",
    "polymarket",
    "pykalshi",
    "py_clob",
}
ALLOWED_CREATE_ORDER_CALLERS = {
    "LiveBrokerFirewall.submit",
    "KalshiSubmitter.submit_limit_order",
}


def _python_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*.py") if p.is_file()]


def _scan_source(source: str) -> list[dict[str, Any]]:
    """Return forbidden hits found in a Python source string."""
    hits: list[dict[str, Any]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [{"kind": "syntax_error", "detail": str(exc)}]

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in FORBIDDEN_CALLS:
                hits.append({"kind": "forbidden_call", "name": name})
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            for alias in node.names:
                full = f"{module}.{alias.name}" if module else alias.name
                if any(forbidden in full.lower() for forbidden in FORBIDDEN_IMPORTS):
                    hits.append({"kind": "forbidden_import", "name": full})

    return hits


def _enclosing_qualname(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    func_name = ""
    class_name = ""
    current: ast.AST | None = node
    while current is not None:
        current = parents.get(current)
        if current is None:
            break
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not func_name:
                func_name = current.name
        elif isinstance(current, ast.ClassDef):
            if not class_name:
                class_name = current.name
    if class_name and func_name:
        return f"{class_name}.{func_name}"
    return func_name or class_name or "<module>"


def _find_create_order_callers(root: Path) -> list[dict[str, Any]]:
    callers: list[dict[str, Any]] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if any(part in rel for part in ("tests/", ".git", "__pycache__", "artifacts/", ".venv", "node_modules")):
            continue
        try:
            source = path.read_text(encoding="utf-8")
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
            if is_create:
                callers.append({
                    "file": rel,
                    "qualname": _enclosing_qualname(node, parents),
                })
    return callers


@pytest.mark.parametrize("path", _python_files(ADAPTERS_DIR), ids=lambda p: p.stem)
def test_promoted_adapters_no_direct_order_bypass(path: Path):
    hits = _scan_source(path.read_text(encoding="utf-8"))
    assert not hits, f"Forbidden live-order path in {path.name}: {hits}"


@pytest.mark.parametrize("path", _python_files(STRATEGIES_DIR), ids=lambda p: p.stem)
def test_repo_strategies_no_direct_order_bypass(path: Path):
    hits = _scan_source(path.read_text(encoding="utf-8"))
    assert not hits, f"Forbidden live-order path in {path.name}: {hits}"


def test_only_firewall_and_submitter_call_create_order():
    callers = _find_create_order_callers(DUMMY_ROOT)
    qualnames = {c["qualname"] for c in callers}
    unexpected = qualnames - ALLOWED_CREATE_ORDER_CALLERS
    assert not unexpected, f"Unexpected create_order callers: {unexpected}; all callers: {callers}"
    assert qualnames == ALLOWED_CREATE_ORDER_CALLERS, (
        f"Expected exactly {ALLOWED_CREATE_ORDER_CALLERS}, got {qualnames}"
    )


def _build_report() -> dict[str, Any]:
    adapter_hits: dict[str, list[dict[str, Any]]] = {}
    for path in _python_files(ADAPTERS_DIR):
        adapter_hits[path.stem] = _scan_source(path.read_text(encoding="utf-8"))

    strategy_hits: dict[str, list[dict[str, Any]]] = {}
    for path in _python_files(STRATEGIES_DIR):
        strategy_hits[path.stem] = _scan_source(path.read_text(encoding="utf-8"))

    callers = _find_create_order_callers(DUMMY_ROOT)
    qualnames = {c["qualname"] for c in callers}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workstream": "Workstream 7: Safety Proofs and Tests",
        "static_scan": {
            "adapters_scanned": len(adapter_hits),
            "adapters_with_hits": [name for name, hits in adapter_hits.items() if hits],
            "strategies_scanned": len(strategy_hits),
            "strategies_with_hits": [name for name, hits in strategy_hits.items() if hits],
            "forbidden_patterns": {
                "calls": sorted(FORBIDDEN_CALLS),
                "imports": sorted(FORBIDDEN_IMPORTS),
            },
        },
        "runtime_proof": {
            "create_order_callers": callers,
            "allowed_callers": sorted(ALLOWED_CREATE_ORDER_CALLERS),
            "unexpected_callers": sorted(qualnames - ALLOWED_CREATE_ORDER_CALLERS),
        },
        "verdict": "PASS" if not (any(adapter_hits.values()) or any(strategy_hits.values()) or (qualnames - ALLOWED_CREATE_ORDER_CALLERS)) else "FAIL",
    }


def test_report_generated():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    report = _build_report()
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))
    assert REPORT_PATH.exists()
    data = json.loads(REPORT_PATH.read_text())
    assert data["verdict"] == "PASS"
    assert data["static_scan"]["adapters_scanned"] > 0
    assert data["static_scan"]["strategies_scanned"] > 0
