import json
import os
from pathlib import Path
from typing import Any

from core.ontology import RepoVerdict
from repo_harvester.incorporation_registry import (
    is_verified_integration,
    load_registry,
    save_registry,
)
from repo_harvester.retry_policy import PENDING_RETRY, PENDING_REVIEW

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


def _upsert_by_adapter(entries: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    name = entry.get("adapter_name")
    entries[:] = [item for item in entries if item.get("adapter_name") != name]
    entries.append(entry)


def _pending_entry(plan: dict[str, Any], adapter_plan: dict[str, Any]) -> dict[str, Any]:
    category = plan.get("category")
    data_only = category in {
        "weather_prediction_market",
        "commodities_energy_agriculture",
    }
    return {
        "repo": plan["repo"],
        "adapter_name": adapter_plan["adapter_name"],
        "category": category,
        "tests_passed": False,
        "test_status": "pending_adapter_specific_tests",
        "integration_status": "pending",
        "integration_kind": adapter_plan.get("integration_kind", "scaffold_only"),
        "upstream_integration_verified": False,
        "production_capability": False,
        "prediction_authority": False,
        "execution_authority": False,
        "data_only": bool(adapter_plan.get("data_only", data_only)),
        "passthrough_model_zoo": bool(adapter_plan.get("passthrough_model_zoo", False)),
    }


def incorporate_adapter_plans(require_tests: bool = True):
    """Stage adapter plans for verification; never waive evidence requirements.

    ``require_tests`` remains in the signature for compatibility, but ``False``
    no longer grants incorporation authority. A plan describes intended work;
    it is not proof that the upstream repository is actually integrated.
    """

    registry = load_registry()
    plans = load_adapter_plans_v2()
    pending = []
    skipped = []
    for plan in plans:
        verdict = plan.get("verdict")
        if verdict in {PENDING_RETRY, PENDING_REVIEW}:
            registry["transient_failures"].append(
                {
                    "repo": plan.get("repo"),
                    "verdict": verdict,
                    "reason": "harvest evidence incomplete",
                }
            )
            skipped.append({"repo": plan.get("repo"), "reason": verdict})
            continue
        if plan.get("verdict") != RepoVerdict.ADAPTER_TARGET.value:
            skipped.append({"repo": plan["repo"], "reason": "not adapter target"})
            continue
        for p in plan.get("plans", []):
            entry = _pending_entry(plan, p)
            if not require_tests:
                entry["test_status"] = "test_waiver_refused"
            _upsert_by_adapter(registry["pending_tests"], entry)
            registry["incorporated"] = [
                item
                for item in registry["incorporated"]
                if item.get("adapter_name") != entry["adapter_name"]
                or is_verified_integration(item)
            ]
            pending.append(entry)
    save_registry(registry)
    return {
        "incorporated": [],
        "pending": pending,
        "skipped": skipped,
        "test_bypass_honored": False,
    }


def approve_adapter_tests(
    adapter_name: str,
    *,
    evidence: dict[str, Any] | None = None,
) -> bool:
    """Approve only a real, adapter-specific upstream integration.

    Structural import/schema/firewall tests for generated pass-through shells do
    not establish production capability. Callers must provide a durable report
    digest and prove that source-specific integration code was exercised.
    """

    registry = load_registry()
    evidence = evidence or {}
    approved = False
    retained_pending: list[dict[str, Any]] = []
    for entry in registry["pending_tests"]:
        if entry.get("adapter_name") != adapter_name:
            retained_pending.append(entry)
            continue

        candidate = {
            **entry,
            "tests_passed": evidence.get("adapter_specific_tests_passed") is True,
            "test_status": (
                "passed_adapter_specific"
                if evidence.get("adapter_specific_tests_passed") is True
                else "approval_refused_missing_adapter_specific_tests"
            ),
            "upstream_integration_verified": (
                evidence.get("upstream_integration_verified") is True
            ),
            "production_capability": evidence.get("production_capability") is True,
            "prediction_authority": evidence.get("prediction_authority") is True,
            "execution_authority": False,
            "test_report_sha256": evidence.get("test_report_sha256"),
        }
        if entry.get("passthrough_model_zoo") is True:
            candidate["test_status"] = "approval_refused_model_zoo_passthrough"
        if entry.get("integration_kind") != "upstream_adapter":
            candidate["test_status"] = "approval_refused_scaffold_only"

        if is_verified_integration(candidate):
            candidate["integration_status"] = "incorporated_verified"
            _upsert_by_adapter(registry["incorporated"], candidate)
            approved = True
        else:
            candidate["tests_passed"] = False
            candidate["production_capability"] = False
            candidate["prediction_authority"] = False
            retained_pending.append(candidate)

    registry["pending_tests"] = retained_pending
    save_registry(registry)
    return approved


def get_allowed_adapter_names() -> set[str]:
    registry = load_registry()
    base = {"kalshi_live_firewall_adapter", "kalshi_official_reference_adapter", "kalshi_python_sdk_adapter", "pykalshi_reference_adapter"}
    base.update(
        entry["adapter_name"]
        for entry in registry["incorporated"]
        if is_verified_integration(entry)
    )
    return base
