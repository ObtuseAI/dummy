import json
import os
from pathlib import Path
from typing import Any

from repo_harvester.lifecycle import (
    DORMANT,
    VERIFIED_CHALLENGER,
    dormant_adapter_record,
)

# Default (production) location. Tests set DUMMY_HARVESTER_ROOT to a tmp dir
# (see tests/conftest.py) so suite runs never write into the real artifact;
# the module-level symbol stays patchable for callers that re-point it.
REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "artifacts" / "repo_harvester" / "incorporation_registry.json"
REGISTRY_SCHEMA_VERSION = 3


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
        "verified_integration_count": 0,
        "pending_adapter_count": 0,
        "dormant_adapter_count": 0,
        "incorporation_summary": (
            "0 verified challenger adapters; 0 dormant unverified adapters."
        ),
    }


def is_verified_integration(entry: dict[str, Any]) -> bool:
    """Return whether an entry has evidence beyond scaffold/structural tests.

    A historical ``tests_passed: true`` flag is deliberately insufficient. It
    only proved that a generated Python shell imported and called Dummy's own
    baseline. Production capability requires an adapter-specific upstream
    integration, a durable test report, a challenger-grade report, a pinned
    upstream revision, and explicit prediction authority.
    """

    return all(
        (
            entry.get("tests_passed") is True,
            entry.get("test_status") == "passed_adapter_specific",
            entry.get("lifecycle_status") == VERIFIED_CHALLENGER,
            entry.get("integration_kind") == "upstream_adapter",
            entry.get("upstream_integration_verified") is True,
            bool(entry.get("upstream_revision")),
            entry.get("challenger_graded") is True,
            entry.get("challenger_grade_status") == "PASSED",
            entry.get("production_capability") is True,
            entry.get("prediction_authority") is True,
            entry.get("data_only") is not True,
            bool(entry.get("test_report_sha256")),
            bool(entry.get("challenger_report_sha256")),
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
        # A historical incorporated row that lacks the complete upstream and
        # challenger evidence contract is not incorporated. Demote it to the
        # single DORMANT inventory instead of trusting a stale boolean.
        verified: list[dict[str, Any]] = []
        dormant_by_name: dict[str, dict[str, Any]] = {}
        for entry in registry["incorporated"]:
            if not isinstance(entry, dict):
                registry["registry_status"] = "MALFORMED_FAIL_CLOSED"
                continue
            if is_verified_integration(entry):
                verified.append(entry)
            elif entry.get("adapter_name"):
                dormant_by_name[str(entry["adapter_name"])] = dormant_adapter_record(
                    entry,
                    reason="historical_incorporation_claim_missing_complete_evidence",
                )
        for entry in registry["pending_tests"]:
            if not isinstance(entry, dict) or not entry.get("adapter_name"):
                registry["registry_status"] = "MALFORMED_FAIL_CLOSED"
                continue
            previous_status = entry.get("test_status")
            normalized = dormant_adapter_record(entry)
            if previous_status not in {None, "DORMANT_UNVERIFIED"}:
                normalized["last_verification_attempt_status"] = previous_status
            dormant_by_name[str(entry["adapter_name"])] = normalized

        registry["schema_version"] = REGISTRY_SCHEMA_VERSION
        registry["incorporated"] = sorted(
            verified, key=lambda entry: str(entry.get("adapter_name", ""))
        )
        registry["pending_tests"] = sorted(
            dormant_by_name.values(),
            key=lambda entry: str(entry.get("adapter_name", "")),
        )
        registry["verified_integration_count"] = len(registry["incorporated"])
        registry["pending_adapter_count"] = len(registry["pending_tests"])
        registry["dormant_adapter_count"] = len(registry["pending_tests"])
        if registry["pending_tests"]:
            registry["registry_status"] = "DORMANT_UNVERIFIED"
        registry["incorporation_summary"] = incorporation_summary(registry)
        return registry
    return empty_registry()


def incorporation_summary(registry: dict[str, Any]) -> str:
    """One plain sentence stating how many adapters are actually incorporated.

    The counts already live in the artifact, but only as fields a reader has to
    assemble. The 2026-07-24 external audit had to derive "0 of 43 adapters
    ever incorporated" by hand; the registry now says it outright.
    """
    incorporated = registry.get("incorporated")
    dormant = registry.get("pending_tests")
    done = len(incorporated) if isinstance(incorporated, list) else 0
    waiting = len(dormant) if isinstance(dormant, list) else 0
    return (
        f"{done} verified challenger adapters; {waiting} dormant unverified "
        "adapters. DORMANT adapters have no prediction, trade-proposal or "
        "execution authority, and a passing structural test does not activate one."
    )


def save_registry(registry: dict):
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(registry)
    payload["schema_version"] = REGISTRY_SCHEMA_VERSION
    # Recomputed on every write from the lists themselves, so the headline can
    # never drift from the rows it summarises.
    for key in ("incorporated", "pending_tests"):
        if not isinstance(payload.get(key), list):
            payload[key] = []
    payload["verified_integration_count"] = len(payload["incorporated"])
    payload["pending_adapter_count"] = len(payload["pending_tests"])
    payload["dormant_adapter_count"] = len(payload["pending_tests"])
    payload["registry_status"] = (
        "DORMANT_UNVERIFIED"
        if payload["pending_tests"]
        else "VERIFIED_INTEGRATIONS_ONLY"
    )
    payload["incorporation_summary"] = incorporation_summary(payload)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(path)


def register_plan(plan: dict, tests_passed: bool = False):
    registry = load_registry()
    entry = dormant_adapter_record(
        {
            "repo": plan["repo"],
            "adapter_name": (
                plan["plans"][0]["adapter_name"] if plan["plans"] else None
            ),
            "last_verification_attempt_status": (
                "legacy_boolean_not_sufficient"
                if tests_passed
                else "not_attempted"
            ),
        }
    )
    registry["pending_tests"].append(entry)
    save_registry(registry)


def dashboard_registry_payload() -> dict[str, Any]:
    """Return a bounded read-only registry view for the canonical dashboard."""

    registry = load_registry()
    verified = registry["incorporated"]
    dormant = registry["pending_tests"]
    rows = [
        {
            "adapter_name": entry.get("adapter_name"),
            "repo": entry.get("repo"),
            "category": entry.get("category"),
            "lifecycle_status": entry.get("lifecycle_status", VERIFIED_CHALLENGER),
            "upstream_integration_verified": bool(
                entry.get("upstream_integration_verified")
            ),
            "challenger_graded": bool(entry.get("challenger_graded")),
            "production_capability": bool(entry.get("production_capability")),
            "prediction_authority": bool(entry.get("prediction_authority")),
            "execution_authority": bool(entry.get("execution_authority")),
            "dormant_reason": entry.get("dormant_reason"),
        }
        for entry in [*verified, *dormant]
    ]
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "registry_status": registry["registry_status"],
        "verified_challenger_count": len(verified),
        "dormant_adapter_count": len(dormant),
        "inventory_count": len(rows),
        "all_unverified_adapters_dormant": all(
            row["lifecycle_status"] == DORMANT
            for row in rows
            if not row["upstream_integration_verified"]
        ),
        "authority": {
            "prediction": any(row["prediction_authority"] for row in rows),
            "execution": any(row["execution_authority"] for row in rows),
        },
        "summary": registry["incorporation_summary"],
        "adapters": rows,
    }
