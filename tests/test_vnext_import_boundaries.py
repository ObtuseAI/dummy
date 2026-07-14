from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VNEXT_ROOT = ROOT / "dummy"
FORBIDDEN_IMPORTS = (
    "dotenv",
    "execution",
    "kalshi",
    "live_firewall",
    "model_router.credential_source",
    "core.proof_authority",
    "core.proof_lock",
    "core.second_proof_lock",
    "core.second_proof_runner",
)


def _matches_forbidden(module: str) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORTS)


def test_vnext_research_package_cannot_import_credentials_or_execution() -> None:
    violations: list[str] = []
    for path in sorted(VNEXT_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if _matches_forbidden(module):
                    violations.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{module}")

    assert violations == []


def test_vnext_research_package_cannot_read_environment_credentials() -> None:
    violations: list[str] = []
    for path in sorted(VNEXT_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "os" and node.attr in {"environ", "getenv"}:
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:os.{node.attr}"
                    )
            if isinstance(node, ast.Name) and node.id in {"environ", "getenv"}:
                violations.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{node.id}")

    assert violations == []
