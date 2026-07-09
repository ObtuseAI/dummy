import json
import os
from pathlib import Path

# Default (production) location. Tests set DUMMY_HARVESTER_ROOT to a tmp dir
# (see tests/conftest.py) so suite runs never write into the real artifact;
# the module-level symbol stays patchable for callers that re-point it.
REGISTRY_PATH = Path("C:/src/engine/dummy/artifacts/repo_harvester/incorporation_registry.json")


def _registry_path() -> Path:
    root = os.environ.get("DUMMY_HARVESTER_ROOT")
    if root:
        return Path(root) / "incorporation_registry.json"
    return REGISTRY_PATH


def load_registry() -> dict:
    path = _registry_path()
    if path.exists():
        return json.loads(path.read_text())
    return {"incorporated": [], "rejected": [], "pending_tests": []}


def save_registry(registry: dict):
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, default=str))


def register_plan(plan: dict, tests_passed: bool = False):
    registry = load_registry()
    entry = {"repo": plan["repo"], "adapter_name": plan["plans"][0]["adapter_name"] if plan["plans"] else None, "tests_passed": tests_passed}
    if tests_passed:
        registry["incorporated"].append(entry)
    else:
        registry["pending_tests"].append(entry)
    save_registry(registry)
