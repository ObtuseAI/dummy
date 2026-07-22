from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ontology import RepoVerdict
from repo_harvester.adapter_planner import DATA_ONLY_CATEGORIES, MODEL_ZOO_CATEGORY

ARTIFACTS = Path("C:/src/engine/dummy/artifacts/repo_harvester")
PLAN_PATH = ARTIFACTS / "adapter_plan_v3.json"
PROMOTED_DIR = Path("C:/src/engine/dummy/adapters/promoted")
DUMMY_ARTIFACTS = Path("C:/src/engine/dummy/artifacts/dummy")

_FORBIDDEN_LIVE_ORDER_PATHS = [
    "create_order",
    "portfolio/orders",
    "orders/{order_id}",
    "cancel_order",
    "market_order",
    "submit_order",
    "polymarket",
]

_RISK_HIT_KEYS = [
    "direct_order_hits",
    "kalshi_order_hits",
    "polymarket_order_hits",
    "private_key_hits",
    "api_secret_hits",
]

_CAPABILITY_HIT_KEYS = [
    "strategy_hits",
    "forecast_hits",
    "risk_hits",
    "arbitrage_hits",
    "websocket_hits",
    "settlement_hits",
    "dashboard_hits",
    "sports_hits",
    "weather_hits",
    "stocks_hits",
    "commodities_hits",
    "crypto_hits",
]

_REQUIRED_TESTS = [
    "import",
    "scaffold_abstention",
    "no_secret_leak",
    "no_direct_order_path",
    "firewall_routing",
    "rejected_repo_isolation",
]


def _safe_module_name(adapter_name: str) -> str:
    """Return a valid Python module filename for an adapter name."""
    return re.sub(r"[^0-9a-zA-Z_]", "_", adapter_name).lower()


def _pascal_class_name(adapter_name: str) -> str:
    """Derive a PascalCase class name from an adapter_name such as foo_bar_adapter."""
    sanitized = re.sub(r"[^0-9a-zA-Z_]", "_", adapter_name)
    parts = [p for p in sanitized.split("_") if p]
    return "".join(p[0].upper() + p[1:] for p in parts)


def load_accepted_plans(path: Path | None = None) -> list[dict[str, Any]]:
    """Load the 64 accepted V3 adapter plans."""
    plan_file = path or PLAN_PATH
    data = json.loads(plan_file.read_text())
    return data.get("plans", [])


def _detect_capabilities(scan_summary: dict[str, Any]) -> list[str]:
    caps: list[str] = []
    for key in _CAPABILITY_HIT_KEYS:
        hits = scan_summary.get(key, [])
        if hits:
            caps.append(key.replace("_hits", ""))
    return caps


def _detect_risks(scan_summary: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    for key in _RISK_HIT_KEYS:
        hits = scan_summary.get(key, [])
        if hits:
            risks.append(key.replace("_hits", ""))
    return risks


def build_promotion_records(path: Path | None = None) -> dict[str, Any]:
    """Split accepted plans by verdict and build promotion metadata records."""
    plans = load_accepted_plans(path)
    records: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(PLAN_PATH),
        "total_accepted": len(plans),
        "direct_dependency_candidates": [],
        "adapter_targets": [],
        "reference_only_strategy_mines": [],
    }

    for plan in plans:
        verdict = plan.get("verdict", "")
        scan_summary = plan.get("scan_summary", {})
        plan_entry = plan.get("plans", [{}])[0]
        adapter_name = plan_entry.get("adapter_name") if plan_entry else None
        category = plan.get("category")
        data_only = category in DATA_ONLY_CATEGORIES
        passthrough_model_zoo = category == MODEL_ZOO_CATEGORY

        record = {
            "repo": plan.get("repo"),
            "category": category,
            "verdict": verdict,
            "verdict_reasons": plan.get("verdict_reasons", []),
            "adapter_name": adapter_name,
            "detected_capabilities": _detect_capabilities(scan_summary),
            "detected_risks": _detect_risks(scan_summary),
            "required_tests": _REQUIRED_TESTS,
            "permitted_dummy_interface": ["to_native_forecast"],
            "forbidden_live_order_paths": _FORBIDDEN_LIVE_ORDER_PATHS,
            "integration_status": "pending",
            "integration_kind": "scaffold_only",
            "test_status": "pending_adapter_specific_tests",
            "tests_passed": False,
            "structural_tests_are_capability_proof": False,
            "upstream_integration_verified": False,
            "production_capability": False,
            "prediction_authority": False,
            "execution_authority": False,
            "data_only": data_only,
            "passthrough_model_zoo": passthrough_model_zoo,
        }

        if verdict == RepoVerdict.DIRECT_DEPENDENCY_CANDIDATE.value:
            records["direct_dependency_candidates"].append(record)
        elif verdict == RepoVerdict.ADAPTER_TARGET.value:
            record["module_name"] = _safe_module_name(adapter_name or "unknown")
            record["class_name"] = _pascal_class_name(adapter_name or "unknown")
            records["adapter_targets"].append(record)
        elif verdict == RepoVerdict.REFERENCE_MINE.value:
            records["reference_only_strategy_mines"].append(record)
        else:
            # Accepted plans are expected to be one of the three verdicts above.
            records["reference_only_strategy_mines"].append(record)

    return records


def _adapter_module_source(
    adapter_name: str,
    class_name: str,
    *,
    category: str | None,
    data_only: bool,
    passthrough_model_zoo: bool,
) -> str:
    return f'''from __future__ import annotations

from adapters.base import DummyAdapter
from core.ontology import Forecast


class {class_name}(DummyAdapter):
    """Non-authoritative research scaffold for {adapter_name}.

    No source-specific upstream integration is implemented here. Structural
    import tests cannot turn this shell into a tested model or production
    capability, so it always abstains until replaced by a verified adapter.
    """

    name = {adapter_name!r}
    CATEGORY = {category!r}
    FORBIDDEN_PATHS = {_FORBIDDEN_LIVE_ORDER_PATHS!r}
    INTEGRATION_STATUS = "scaffold_only"
    TEST_STATUS = "pending_adapter_specific_tests"
    UPSTREAM_INTEGRATION_VERIFIED = False
    PRODUCTION_CAPABILITY = False
    PREDICTION_AUTHORITY = False
    EXECUTION_AUTHORITY = False
    DATA_ONLY = {data_only!r}
    PASSTHROUGH_MODEL_ZOO = {passthrough_model_zoo!r}

    def to_native_forecast(self, raw) -> Forecast | None:
        del raw
        return None
'''


def generate_promoted_adapter_modules(records: dict[str, Any] | None = None) -> list[str]:
    """Write one fail-closed research scaffold per ADAPTER_TARGET record."""
    if records is None:
        records = build_promotion_records()
    PROMOTED_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for record in records["adapter_targets"]:
        adapter_name = record["adapter_name"]
        class_name = record["class_name"]
        module_name = record["module_name"]
        module_path = PROMOTED_DIR / f"{module_name}.py"
        module_path.write_text(
            _adapter_module_source(
                adapter_name,
                class_name,
                category=record.get("category"),
                data_only=bool(record.get("data_only")),
                passthrough_model_zoo=bool(record.get("passthrough_model_zoo")),
            )
        )
        written.append(str(module_path))

    # Refresh the package __init__.py so adapters.promoted exports the registry.
    _write_promoted_init(records["adapter_targets"])
    return written


def _write_promoted_init(adapter_targets: list[dict[str, Any]]) -> None:
    lines = [
        "from __future__ import annotations",
        "",
        "# Generated modules are research scaffolds, not verified integrations.",
        "PROMOTED_ADAPTER_NAMES: list[str] = []",
        "PROMOTED_MODULES: dict[str, str] = {}",
        "",
        "PENDING_ADAPTER_NAMES: list[str] = [",
    ]
    for record in adapter_targets:
        lines.append(f'    "{record["adapter_name"]}",')
    lines.extend([
        "]",
        "",
        "PENDING_MODULES: dict[str, str] = {",
    ])
    for record in adapter_targets:
        lines.append(f'    "{record["adapter_name"]}": "{record["module_name"]}",')
    lines.extend([
        "}",
        "",
    ])
    (PROMOTED_DIR / "__init__.py").write_text("\n".join(lines).rstrip() + "\n")


def write_promotion_report(records: dict[str, Any], path: Path | None = None) -> Path:
    """Write adapter_promotion_report_v1.json."""
    report_path = path or DUMMY_ARTIFACTS / "adapter_promotion_report_v1.json"
    DUMMY_ARTIFACTS.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(PLAN_PATH),
        "total_accepted": records["total_accepted"],
        "direct_dependency_count": len(records["direct_dependency_candidates"]),
        "adapter_target_count": len(records["adapter_targets"]),
        "reference_mine_count": len(records["reference_only_strategy_mines"]),
        "verified_integration_count": 0,
        "production_capability_count": 0,
        "prediction_authority_count": 0,
        "execution_authority_count": 0,
        "status": "SCAFFOLDS_PENDING_ADAPTER_SPECIFIC_VERIFICATION",
        "forbidden_live_order_paths": _FORBIDDEN_LIVE_ORDER_PATHS,
        "records": records,
    }
    report_path.write_text(json.dumps(report, indent=2, default=str))
    return report_path


def update_incorporation_registry(records: dict[str, Any]) -> Path:
    """Synchronize plans without converting generated shells into integrations."""
    from repo_harvester.incorporation_registry import (
        _registry_path,
        is_verified_integration,
        load_registry,
        save_registry,
    )

    registry = load_registry()
    registry.setdefault("incorporated", [])
    registry.setdefault("rejected", [])
    registry.setdefault("pending_tests", [])

    target_by_name = {
        record["adapter_name"]: record
        for record in records["adapter_targets"]
        if record.get("adapter_name")
    }

    verified: list[dict[str, Any]] = []
    demoted: list[dict[str, Any]] = []
    for existing in registry["incorporated"]:
        if is_verified_integration(existing):
            verified.append(existing)
            continue
        demoted.append(
            {
                **existing,
                "tests_passed": False,
                "test_status": "legacy_structural_claim_demoted",
                "integration_status": "pending",
                "integration_kind": "scaffold_only",
                "upstream_integration_verified": False,
                "production_capability": False,
                "prediction_authority": False,
                "execution_authority": False,
            }
        )
    registry["incorporated"] = verified
    verified_names = {
        entry.get("adapter_name") for entry in verified if entry.get("adapter_name")
    }

    pending_by_name = {
        entry.get("adapter_name"): entry
        for entry in [*registry["pending_tests"], *demoted]
        if entry.get("adapter_name")
    }
    for adapter_name, record in target_by_name.items():
        if adapter_name in verified_names:
            pending_by_name.pop(adapter_name, None)
            continue
        previous = pending_by_name.get(adapter_name, {})
        pending_by_name[adapter_name] = {
            **previous,
            "repo": record["repo"],
            "adapter_name": adapter_name,
            "category": record.get("category"),
            "tests_passed": False,
            "test_status": "pending_adapter_specific_tests",
            "integration_status": "pending",
            "integration_kind": "scaffold_only",
            "upstream_integration_verified": False,
            "production_capability": False,
            "prediction_authority": False,
            "execution_authority": False,
            "data_only": bool(record.get("data_only")),
            "passthrough_model_zoo": bool(record.get("passthrough_model_zoo")),
        }
    registry["pending_tests"] = sorted(
        pending_by_name.values(), key=lambda entry: str(entry.get("adapter_name", ""))
    )

    registry["direct_dependency_candidates"] = [
        {
            "repo": record["repo"],
            "category": record.get("category"),
            "adapter_name": record.get("adapter_name"),
            "review_status": "pending_dependency_review",
            "production_capability": False,
            "prediction_authority": False,
            "execution_authority": False,
        }
        for record in records["direct_dependency_candidates"]
    ]
    registry["reference_only_strategy_mines"] = [
        {"repo": r["repo"], "category": r["category"], "adapter_name": r["adapter_name"]}
        for r in records["reference_only_strategy_mines"]
    ]

    registry["synced_from"] = "adapter_plan_v3.json"
    registry["registry_status"] = (
        "PENDING_VERIFICATION_FAIL_CLOSED"
        if registry["pending_tests"]
        else "VERIFIED_INTEGRATIONS_ONLY"
    )
    registry["verified_integration_count"] = len(registry["incorporated"])
    registry["pending_adapter_count"] = len(registry["pending_tests"])
    registry["generated_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry)
    return _registry_path()


if __name__ == "__main__":
    recs = build_promotion_records()
    modules = generate_promoted_adapter_modules(recs)
    report_path = write_promotion_report(recs)
    registry_path = update_incorporation_registry(recs)
    print(f"Wrote {len(modules)} pending adapter scaffolds")
    print(f"Report: {report_path}")
    print(f"Registry: {registry_path}")
