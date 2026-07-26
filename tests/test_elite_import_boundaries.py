"""Static boundaries for research observers and the read-only validator."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ROOTS = (
    ROOT / "dummy" / "autoresearch",
    ROOT / "dummy" / "intelligence_lab",
    ROOT / "autonomy" / "market_observer",
)
FORBIDDEN_IMPORTS = (
    "dotenv",
    "execution",
    "kalshi",
    "live_firewall",
    "core.caps_authority",
    "core.live_submit_state",
    "core.proof_authority",
    "core.proof_lock",
    "model_router.credential_source",
)
FORBIDDEN_SINKS = {
    "amend_order",
    "cancel_order",
    "create_order",
    "place_order",
    "register_caps_authority",
    "submit_limit_order",
    "write_live_submit_config",
}
AUTHORITY_PATH_MARKERS = (
    "configs/live_submit.json",
    "configs/caps.json",
    "operator_authority_pack",
)
ALLOWED_NON_SECRET_ENV = {"DUMMY_MARKET_OBSERVER_ROOT"}
SANDBOX_FIXED_ENV = {
    "DUMMY_RESEARCH_SANDBOX": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
}


def _python_files() -> list[Path]:
    return [
        path
        for root in RESEARCH_ROOTS
        if root.exists()
        for path in sorted(root.rglob("*.py"))
    ]


def _module_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return (node.module,)
    return ()


def _is_forbidden_module(module: str) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_IMPORTS
    )


def test_research_and_market_observers_cannot_import_execution_or_authority() -> None:
    violations: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for module in _module_names(node):
                if _is_forbidden_module(module):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{module}"
                    )
    assert violations == []


def test_research_and_market_observers_cannot_call_order_or_authority_sinks() -> None:
    violations: list[str] = []
    for path in _python_files():
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
            if name in FORBIDDEN_SINKS:
                violations.append(
                    f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{name}"
                )
    assert violations == []


def test_research_and_market_observers_cannot_read_process_environment() -> None:
    violations: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr == "getenv"
            ):
                call = parents.get(node)
                key = (
                    call.args[0].value
                    if isinstance(call, ast.Call)
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                    and isinstance(call.args[0].value, str)
                    else None
                )
                if key not in ALLOWED_NON_SECRET_ENV:
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:os.getenv:{key}"
                    )
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr == "environ"
            ):
                outer = parents.get(node)
                call = parents.get(outer) if isinstance(outer, ast.Attribute) else None
                key = (
                    call.args[0].value
                    if isinstance(outer, ast.Attribute)
                    and outer.attr == "get"
                    and isinstance(call, ast.Call)
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                    and isinstance(call.args[0].value, str)
                    else None
                )
                if key not in ALLOWED_NON_SECRET_ENV:
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:os.environ:{key}"
                    )
            if (
                isinstance(node, ast.Name)
                and node.id in {"environ", "getenv"}
                and not isinstance(getattr(node, "ctx", None), ast.Store)
            ):
                violations.append(
                    f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{node.id}"
                )
    assert violations == []


def test_isolated_research_executor_uses_only_code_owned_environment() -> None:
    from dummy.autoresearch.isolated_executor import IsolatedResearchExecutor

    assert IsolatedResearchExecutor.sanitized_environment() == SANDBOX_FIXED_ENV


def test_research_and_market_observers_do_not_name_mutable_authority_paths() -> None:
    violations: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            normalized = node.value.replace("\\", "/").lower()
            if any(marker in normalized for marker in AUTHORITY_PATH_MARKERS):
                violations.append(
                    f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
                )
    assert violations == []


def test_elite_validator_has_no_write_network_subprocess_or_application_imports() -> None:
    path = ROOT / "scripts" / "run_dummy_elite_validation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    forbidden_modules = (
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        *FORBIDDEN_IMPORTS,
    )
    forbidden_calls = {
        "mkdir",
        "open",
        "rename",
        "touch",
        "unlink",
        "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        for module in _module_names(node):
            if any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in forbidden_modules
            ):
                violations.append(f"{node.lineno}:import:{module}")
        if isinstance(node, ast.Call):
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            if name in forbidden_calls:
                violations.append(f"{node.lineno}:call:{name}")
    assert violations == []
