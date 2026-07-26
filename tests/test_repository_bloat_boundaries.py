"""Guardrails that keep retired source scaffolds from growing back."""

from __future__ import annotations

import ast
import os
from pathlib import Path

from adapters.promoted import PendingAdapter
from forecasting.hybrid_engine import HybridForecastEngine
from repo_harvester.promotion_engine import generate_promoted_adapter_modules
from strategies.registry import STRATEGIES, STRATEGY_CATALOG

ROOT = Path(__file__).resolve().parents[1]
NON_SOURCE_DIRS = frozenset(
    {
        ".git",
        ".hypothesis",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "site-packages",
        "venv",
    }
)


def _repository_python_files():
    """Yield project Python files without descending into generated environments."""

    for directory, child_directories, filenames in os.walk(ROOT, topdown=True):
        child_directories[:] = sorted(
            name for name in child_directories if name not in NON_SOURCE_DIRS
        )
        base = Path(directory)
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield base / filename


def test_pending_adapter_candidates_use_one_inert_module():
    promoted = ROOT / "adapters" / "promoted"
    assert {path.name for path in promoted.glob("*.py")} == {
        "__init__.py",
        "pending.py",
    }
    assert generate_promoted_adapter_modules({"adapter_targets": []}) == []
    assert PendingAdapter("candidate").to_native_forecast({}) is None


def test_registered_strategies_have_real_evaluation_logic():
    assert len({strategy.name for strategy in STRATEGIES}) == len(STRATEGIES)
    for strategy in STRATEGIES:
        path = Path(__import__(strategy.__class__.__module__, fromlist=["x"]).__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        evaluate = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "evaluate"
        )
        assert not (
            len(evaluate.body) == 1
            and isinstance(evaluate.body[0], ast.Return)
            and isinstance(evaluate.body[0].value, ast.Constant)
            and evaluate.body[0].value.value is None
        ), f"{strategy.name} is a generated constant-abstention scaffold"


def test_strategy_compatibility_lists_are_derived_from_one_catalog():
    research_names = tuple(
        entry.name
        for entry in STRATEGY_CATALOG
        if entry.lifecycle_status == "RESEARCH_ONLY"
    )
    assert tuple(strategy.name for strategy in STRATEGIES) == research_names
    assert all(entry.execution_authority is False for entry in STRATEGY_CATALOG)


def test_legacy_forecast_engine_path_cannot_be_imported():
    assert not (ROOT / "forecasting" / "engine.py").exists()
    assert not hasattr(HybridForecastEngine, "forecast_opinion")

    offenders: list[str] = []
    for path in _repository_python_files():
        text = path.read_text(encoding="utf-8")
        if "forecasting.engine" not in text:
            continue
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "forecasting.engine":
                offenders.append(str(path.relative_to(ROOT)))
            if isinstance(node, ast.Import) and any(
                alias.name == "forecasting.engine" for alias in node.names
            ):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_runtime_packages_do_not_import_report_archive():
    runtime_roots = (
        "autonomy",
        "core",
        "dummy",
        "forecasting",
        "kalshi",
        "live_firewall",
        "model_router",
        "risk",
        "services",
    )
    offenders: list[str] = []
    for root_name in runtime_roots:
        root = ROOT / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "archive.report_scripts" in text or "archive.routes" in text:
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
