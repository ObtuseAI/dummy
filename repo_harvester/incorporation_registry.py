import json
import os
from pathlib import Path
from typing import Any

# Default (production) location. Tests set DUMMY_HARVESTER_ROOT to a tmp dir
# (see tests/conftest.py) so suite runs never write into the real artifact;
# the module-level symbol stays patchable for callers that re-point it.
REGISTRY_PATH = Path("C:/src/engine/dummy/artifacts/repo_harvester/incorporation_registry.json")
REGISTRY_SCHEMA_VERSION = 2


def empty_registry(*, status: str = "OK") -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "registry_status": status,
        "incorporated": [],
        "rejected": [],
        "pending_tests": [],
        "transient_failures": [],
        "direct_dependency_candidates": [],
        "reference_only_strategy_mines": [],
    }


def is_verified_integration(entry: dict[str, Any]) -> bool:
    """Return whether an entry has evidence beyond scaffold/structural tests.

    A historical ``tests_passed: true`` flag is deliberately insufficient. It
    only proved that a generated Python shell imported and called Dummy's own
    baseline. Production capability requires an adapter-specific upstream
    integration, a durable test report, and explicit prediction authority.
    """

    return all(
        (
            entry.get("tests_passed") is True,
            entry.get("test_status") == "passed_adapter_specific",
            entry.get("integration_kind") == "upstream_adapter",
            entry.get("upstream_integration_verified") is True,
            entry.get("production_capability") is True,
            entry.get("prediction_authority") is True,
            entry.get("data_only") is not True,
            bool(entry.get("test_report_sha256")),
        )
    )


def _registry_path() -> Path:
    root = os.environ.get("DUMMY_HARVESTER_ROOT")
    if root:
        return Path(root) / "incorporation_registry.json"
    return REGISTRY_PATH


def load_registry() -> dict:
    path = _registry_path()
    if path.exists():
        try:
            loaded = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return empty_registry(status="CORRUPT_FAIL_CLOSED")
        if not isinstance(loaded, dict):
            return empty_registry(status="MALFORMED_FAIL_CLOSED")
        registry = empty_registry(status=str(loaded.get("registry_status", "OK")))
        registry.update(loaded)
        for key in (
            "incorporated",
            "rejected",
            "pending_tests",
            "transient_failures",
            "direct_dependency_candidates",
            "reference_only_strategy_mines",
        ):
            if not isinstance(registry.get(key), list):
                registry[key] = []
                registry["registry_status"] = "MALFORMED_FAIL_CLOSED"
        registry["schema_version"] = REGISTRY_SCHEMA_VERSION
        return registry
    return empty_registry()


def save_registry(registry: dict):
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(registry)
    payload["schema_version"] = REGISTRY_SCHEMA_VERSION
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(path)


def register_plan(plan: dict, tests_passed: bool = False):
    registry = load_registry()
    entry = {
        "repo": plan["repo"],
        "adapter_name": plan["plans"][0]["adapter_name"] if plan["plans"] else None,
        "tests_passed": False,
        "test_status": (
            "legacy_boolean_not_sufficient" if tests_passed else "pending_adapter_specific_tests"
        ),
        "integration_kind": "scaffold_only",
        "upstream_integration_verified": False,
        "production_capability": False,
        "prediction_authority": False,
        "execution_authority": False,
    }
    registry["pending_tests"].append(entry)
    save_registry(registry)
