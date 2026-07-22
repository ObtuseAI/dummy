import json
import os
from pathlib import Path

from repo_harvester.incorporation_engine import (
    approve_adapter_tests,
    get_allowed_adapter_names,
    incorporate_adapter_plans,
)
from repo_harvester.incorporation_registry import load_registry, save_registry
from core.ontology import RepoVerdict


def _write_plan(*, integration_kind: str = "scaffold_only", category: str = "sports_prediction_odds") -> None:
    """Stage one adapter plan inside the tmp harvester root (conftest routes
    DUMMY_HARVESTER_ROOT to tmp, so nothing touches the real artifact)."""
    plan = {
        "repo": "x/y",
        "category": category,
        "verdict": RepoVerdict.ADAPTER_TARGET.value,
        "plans": [{
            "adapter_name": "y_adapter",
            "emits_native_types": False,
            "integration_kind": integration_kind,
            "notes": "",
        }],
    }
    root = Path(os.environ["DUMMY_HARVESTER_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    (root / "adapter_plan_v2.json").write_text(json.dumps({"plans": [plan]}))


def test_incorporate_only_adapter_targets():
    _write_plan()
    result = incorporate_adapter_plans(require_tests=True)
    assert len(result["incorporated"]) == 0
    registry = load_registry()
    pending = next(e for e in registry["pending_tests"] if e["adapter_name"] == "y_adapter")
    assert pending["test_status"] == "pending_adapter_specific_tests"
    assert pending["production_capability"] is False
    assert pending["prediction_authority"] is False


def test_structural_scaffold_cannot_be_approved_into_production():
    _write_plan()
    incorporate_adapter_plans(require_tests=True)
    assert "y_adapter" not in get_allowed_adapter_names()
    approved = approve_adapter_tests(
        "y_adapter",
        evidence={
            "adapter_specific_tests_passed": True,
            "upstream_integration_verified": True,
            "production_capability": True,
            "prediction_authority": True,
            "test_report_sha256": "a" * 64,
        },
    )
    assert approved is False
    assert "y_adapter" not in get_allowed_adapter_names()
    registry = load_registry()
    assert registry["incorporated"] == []
    assert registry["pending_tests"][0]["test_status"] == "approval_refused_scaffold_only"


def test_verified_upstream_adapter_requires_complete_evidence():
    _write_plan(integration_kind="upstream_adapter")
    incorporate_adapter_plans(require_tests=True)

    assert approve_adapter_tests("y_adapter", evidence={}) is False
    assert "y_adapter" not in get_allowed_adapter_names()

    approved = approve_adapter_tests(
        "y_adapter",
        evidence={
            "adapter_specific_tests_passed": True,
            "upstream_integration_verified": True,
            "production_capability": True,
            "prediction_authority": True,
            "test_report_sha256": "b" * 64,
        },
    )
    assert approved is True
    assert "y_adapter" in get_allowed_adapter_names()


def test_require_tests_false_cannot_waive_governance():
    _write_plan(integration_kind="upstream_adapter")
    result = incorporate_adapter_plans(require_tests=False)
    assert result["incorporated"] == []
    assert result["test_bypass_honored"] is False
    assert "y_adapter" not in get_allowed_adapter_names()
    assert load_registry()["pending_tests"][0]["test_status"] == "test_waiver_refused"


def test_legacy_boolean_test_claim_is_not_production_evidence():
    save_registry({
        "incorporated": [{
            "repo": "legacy/model-zoo",
            "adapter_name": "legacy_adapter",
            "tests_passed": True,
        }],
        "rejected": [],
        "pending_tests": [],
    })
    assert "legacy_adapter" not in get_allowed_adapter_names()


def test_data_only_adapter_never_gets_prediction_authority():
    _write_plan(integration_kind="upstream_adapter", category="weather_prediction_market")
    incorporate_adapter_plans(require_tests=True)
    approved = approve_adapter_tests(
        "y_adapter",
        evidence={
            "adapter_specific_tests_passed": True,
            "upstream_integration_verified": True,
            "production_capability": True,
            "prediction_authority": True,
            "test_report_sha256": "c" * 64,
        },
    )
    assert approved is False
    assert "y_adapter" not in get_allowed_adapter_names()
    entry = load_registry()["pending_tests"][0]
    assert entry["data_only"] is True
    assert entry["prediction_authority"] is False


def test_suite_never_touches_real_registry():
    # The env route must point every registry write into tmp.
    from repo_harvester.incorporation_registry import _registry_path

    assert "artifacts" not in str(_registry_path())
