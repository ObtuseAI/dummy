import json
from pathlib import Path

REGISTRY_PATH = Path("C:/src/engine/dummy/artifacts/repo_harvester/incorporation_registry.json")

def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {"incorporated": [], "rejected": [], "pending_tests": []}

def save_registry(registry: dict):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, default=str))

def register_plan(plan: dict, tests_passed: bool = False):
    registry = load_registry()
    entry = {"repo": plan["repo"], "adapter_name": plan["plans"][0]["adapter_name"] if plan["plans"] else None, "tests_passed": tests_passed}
    if tests_passed:
        registry["incorporated"].append(entry)
    else:
        registry["pending_tests"].append(entry)
    save_registry(registry)
