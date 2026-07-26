"""Stable invariants replacing the retired V4-V105 report-test chains."""

from __future__ import annotations

import ast
from pathlib import Path
import tomllib

import pytest

from predator_mesh.report_runtime import ReportContractError, generate_report_bundle


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "node_modules",
    "runtime",
    "venv",
}


def _project_python_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*.py")
        if not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    ]


def _imported_modules(tree: ast.AST) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module)
    return tuple(modules)


def test_retired_archive_is_not_packaged_or_imported() -> None:
    assert not (ROOT / "archive").exists()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_patterns = project["tool"]["setuptools"]["packages"]["find"]["include"]
    assert not any(pattern == "archive" or pattern.startswith("archive*") for pattern in package_patterns)

    offenders: list[str] = []
    for path in _project_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            module == "archive" or module.startswith("archive.")
            for module in _imported_modules(tree)
        ):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


@pytest.mark.parametrize("version", [4, 19, 20, 59, 60, 105])
def test_retired_report_versions_have_no_runtime_factory(version: int) -> None:
    with pytest.raises(ReportContractError):
        generate_report_bundle(version)


@pytest.mark.parametrize(
    ("sink", "allowed"),
    [
        ("create_order", {"live_firewall/firewall.py"}),
        ("cancel_order", set()),
        ("amend_order", set()),
        ("place_order", set()),
    ],
)
def test_broker_write_sink_topology_is_explicit(
    sink: str,
    allowed: set[str],
) -> None:
    callsites: set[str] = set()
    for path in _project_python_files():
        if path.is_relative_to(ROOT / "tests"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            if name == sink:
                callsites.add(path.relative_to(ROOT).as_posix())
    assert callsites == allowed
