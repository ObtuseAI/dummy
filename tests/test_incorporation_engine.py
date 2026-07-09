import json
import os
from pathlib import Path

from repo_harvester.incorporation_engine import (
    approve_adapter_tests,
    get_allowed_adapter_names,
    incorporate_adapter_plans,
)
from repo_harvester.incorporation_registry import load_registry
from core.ontology import RepoVerdict


def _write_plan() -> None:
    """Stage one adapter plan inside the tmp harvester root (conftest routes
    DUMMY_HARVESTER_ROOT to tmp, so nothing touches the real artifact)."""
    plan = {
        "repo": "x/y",
        "verdict": RepoVerdict.ADAPTER_TARGET.value,
        "plans": [{"adapter_name": "y_adapter", "emits_native_types": True, "notes": ""}],
    }
    root = Path(os.environ["DUMMY_HARVESTER_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    (root / "adapter_plan_v2.json").write_text(json.dumps({"plans": [plan]}))


def test_incorporate_only_adapter_targets():
    _write_plan()
    result = incorporate_adapter_plans(require_tests=True)
    assert len(result["incorporated"]) == 0
    registry = load_registry()
    assert any(e["adapter_name"] == "y_adapter" for e in registry["pending_tests"])


def test_approve_adapter():
    # Self-contained: stage -> incorporate (pending) -> approve -> allowed.
    _write_plan()
    incorporate_adapter_plans(require_tests=True)
    assert "y_adapter" not in get_allowed_adapter_names()
    approve_adapter_tests("y_adapter")
    assert "y_adapter" in get_allowed_adapter_names()


def test_suite_never_touches_real_registry():
    # The env route must point every registry write into tmp.
    from repo_harvester.incorporation_registry import _registry_path

    assert "artifacts" not in str(_registry_path())
