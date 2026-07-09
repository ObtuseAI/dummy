import json
import os
from pathlib import Path
from core.ontology import RepoVerdict
from repo_harvester.incorporation_registry import load_registry, save_registry

ARTIFACTS = Path("C:/src/engine/dummy/artifacts/repo_harvester")


def _artifacts_dir() -> Path:
    # Tests route harvester artifacts to tmp via DUMMY_HARVESTER_ROOT so the
    # suite never writes into the real artifact tree.
    root = os.environ.get("DUMMY_HARVESTER_ROOT")
    return Path(root) if root else ARTIFACTS


def load_adapter_plans_v2() -> list[dict]:
    path = _artifacts_dir() / "adapter_plan_v2.json"
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("plans", [])


def incorporate_adapter_plans(require_tests: bool = True):
    registry = load_registry()
    plans = load_adapter_plans_v2()
    incorporated = []
    rejected = []
    for plan in plans:
        if plan.get("verdict") != RepoVerdict.ADAPTER_TARGET.value:
            rejected.append({"repo": plan["repo"], "reason": "not adapter target"})
            continue
        for p in plan.get("plans", []):
            entry = {"repo": plan["repo"], "adapter_name": p["adapter_name"], "tests_passed": False}
            if require_tests:
                registry["pending_tests"].append(entry)
            else:
                entry["tests_passed"] = True
                registry["incorporated"].append(entry)
                incorporated.append(entry)
    save_registry(registry)
    return {"incorporated": incorporated, "rejected": rejected}


def approve_adapter_tests(adapter_name: str):
    registry = load_registry()
    for entry in registry["pending_tests"]:
        if entry["adapter_name"] == adapter_name:
            entry["tests_passed"] = True
            registry["incorporated"].append(entry)
    registry["pending_tests"] = [e for e in registry["pending_tests"] if not e.get("tests_passed")]
    save_registry(registry)


def get_allowed_adapter_names() -> set[str]:
    registry = load_registry()
    base = {"kalshi_live_firewall_adapter", "kalshi_official_reference_adapter", "kalshi_python_sdk_adapter", "pykalshi_reference_adapter"}
    base.update(e["adapter_name"] for e in registry["incorporated"] if e.get("tests_passed"))
    return base
