"""Pin the stable boundary between active code and retained report contracts.

Live production code -- everything outside tests/ and archive/ -- must not
import a ``predator_mesh.vNN`` snapshot.  Current status views, report
contracts, and integrity constants have stable homes; no version package may
be reconstructed dynamically.

If this test fails because you added a NEW live dependency on a snapshot
version, that is the point: prefer promoting the code you need out of the
snapshot into a maintained module, so the archive stays archive. Widening the
allow-list should be a deliberate, commented decision.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Directories that are the LIVE surface: not tests, not the archive tree, and
# not predator_mesh itself.
LIVE_DIRS = (
    "autonomy", "core", "dashboard", "dummy", "execution", "forecasting",
    "kalshi", "live_firewall", "model_router", "risk", "scripts", "tools",
)

# Every predator_mesh import live code is currently allowed to make.
ALLOWED_LIVE_IMPORTS = {
    # Shared broker/gate packages, not version snapshots.
    "predator_mesh.brokers",
    "predator_mesh.staged_gate_common",
    "predator_mesh.authority_contracts",
    "predator_mesh.operator_status",
    "predator_mesh.operator_proof_workflows",
    # Sole compatibility facade for retained V106-V304 artifact contracts.
    "predator_mesh.report_runtime",
}

_IMPORT = re.compile(r"\bpredator_mesh(?:\.[A-Za-z_][A-Za-z_0-9]*)*")
_VERSION_IMPORT = re.compile(r"^predator_mesh\.v\d+(?:\.|$)")


def _live_imports() -> dict[str, set[str]]:
    """Map each live file to the predator_mesh roots it references."""
    found: dict[str, set[str]] = {}
    for directory in LIVE_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for match in _IMPORT.findall(text):
                parts = match.split(".")
                # Normalise to the first meaningful level: predator_mesh.<x>.
                root = ".".join(parts[:2]) if len(parts) > 1 else parts[0]
                if root == "predator_mesh":
                    continue          # bare package reference, not a snapshot
                found.setdefault(str(path.relative_to(ROOT)), set()).add(root)
    return found


def test_live_code_touches_only_the_pinned_predator_mesh_surface():
    offenders: dict[str, set[str]] = {}
    for file, roots in _live_imports().items():
        extra = roots - ALLOWED_LIVE_IMPORTS
        if extra:
            offenders[file] = extra
    assert not offenders, (
        "new live dependency on the predator_mesh archive: "
        f"{offenders}. Promote what you need into a maintained module instead "
        "of importing a version snapshot, or widen ALLOWED_LIVE_IMPORTS with a "
        "comment saying why."
    )


def test_live_code_does_not_import_version_snapshots():
    """Historical milestone packages must never regain production authority."""
    versions = {
        root for roots in _live_imports().values() for root in roots
        if re.fullmatch(r"predator_mesh\.v\d+", root)
    }
    assert versions == set(), versions


def _active_version_imports() -> dict[str, set[str]]:
    """Find real Python imports, excluding the retained contract definitions."""

    excluded_roots = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "archive",
        "artifacts",
        "build",
        "dist",
        "runtime",
        "venv",
    }
    offenders: dict[str, set[str]] = {}
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if relative.parts[0] in excluded_roots:
            continue
        if (
            len(relative.parts) >= 2
            and relative.parts[0] == "predator_mesh"
            and re.fullmatch(r"v\d+", relative.parts[1])
        ):
            continue
        if "__pycache__" in relative.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if _VERSION_IMPORT.match(node.module):
                    imports.add(node.module)
            elif isinstance(node, ast.Import):
                imports.update(
                    alias.name
                    for alias in node.names
                    if _VERSION_IMPORT.match(alias.name)
                )
        if imports:
            offenders[str(relative)] = imports
    return offenders


def _dynamic_version_imports() -> dict[str, list[str]]:
    """Reject importlib/__import__ attempts that reconstruct snapshot imports."""

    offenders: dict[str, list[str]] = {}
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if relative.parts[0] in {
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "archive",
            "artifacts",
            "build",
            "dist",
            "runtime",
            "venv",
        }:
            continue
        if "__pycache__" in relative.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        hits: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function_name = ""
            if isinstance(node.func, ast.Name):
                function_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                function_name = node.func.attr
            if function_name not in {
                "__import__",
                "find_spec",
                "import_module",
            }:
                continue
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(
                argument.value, str
            ):
                expression = argument.value
            elif isinstance(argument, ast.JoinedStr):
                expression = "".join(
                    part.value
                    if isinstance(part, ast.Constant)
                    and isinstance(part.value, str)
                    else "{}"
                    for part in argument.values
                )
            else:
                expression = ast.unparse(argument)
            if "predator_mesh.v" in expression:
                hits.append(f"{function_name}({expression!r})")
        if hits:
            offenders[str(relative)] = hits
    return offenders


def test_active_code_and_tests_do_not_import_version_snapshots() -> None:
    offenders = _active_version_imports()
    assert not offenders, (
        "active code/tests imported retired predator_mesh.vNN snapshots: "
        f"{offenders}. Use a stable module or report_runtime compatibility "
        "facade instead."
    )


def test_active_code_cannot_reconstruct_version_snapshot_imports() -> None:
    offenders = _dynamic_version_imports()
    assert not offenders, (
        "active code dynamically imports retired predator_mesh.vNN snapshots: "
        f"{offenders}"
    )


def test_version_snapshot_sources_are_absent() -> None:
    snapshots = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "predator_mesh").glob("v[0-9]*/**/*.py")
    )
    assert snapshots == []
