import json
from pathlib import Path
from repo_harvester.incorporation_engine import load_adapter_plans_v2, incorporate_adapter_plans, approve_adapter_tests, get_allowed_adapter_names
from repo_harvester.incorporation_registry import load_registry
from core.ontology import RepoVerdict


def test_incorporate_only_adapter_targets(tmp_path):
    plan = {
        "repo": "x/y",
        "verdict": RepoVerdict.ADAPTER_TARGET.value,
        "plans": [{"adapter_name": "y_adapter", "emits_native_types": True, "notes": ""}]
    }
    path = Path("C:/src/engine/dummy/artifacts/repo_harvester/adapter_plan_v2.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"plans": [plan]}))
    result = incorporate_adapter_plans(require_tests=True)
    assert len(result["incorporated"]) == 0
    registry = load_registry()
    assert any(e["adapter_name"] == "y_adapter" for e in registry["pending_tests"])


def test_approve_adapter():
    approve_adapter_tests("y_adapter")
    assert "y_adapter" in get_allowed_adapter_names()
