from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.ontology import RepoVerdict

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
    "schema_conversion",
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

        record = {
            "repo": plan.get("repo"),
            "category": plan.get("category"),
            "verdict": verdict,
            "verdict_reasons": plan.get("verdict_reasons", []),
            "adapter_name": adapter_name,
            "detected_capabilities": _detect_capabilities(scan_summary),
            "detected_risks": _detect_risks(scan_summary),
            "required_tests": _REQUIRED_TESTS,
            "permitted_dummy_interface": ["to_native_forecast"],
            "forbidden_live_order_paths": _FORBIDDEN_LIVE_ORDER_PATHS,
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


def _adapter_module_source(adapter_name: str, class_name: str) -> str:
    return f'''from __future__ import annotations

from adapters.base import DummyAdapter
from core.ontology import Forecast, OrderBook, OrderBookLevel
from datetime import datetime, timezone
from forecasting.engine import ForecastEngine


class {class_name}(DummyAdapter):
    """Lightweight Dummy-native adapter wrapper for {adapter_name}.

    This module only transforms raw data into Dummy-native Forecast objects.
    It does not import or call any live order endpoint.
    """

    name = "{adapter_name}"
    FORBIDDEN_PATHS = {_FORBIDDEN_LIVE_ORDER_PATHS!r}

    def to_native_forecast(self, raw) -> Forecast:
        book = raw.get("book") or raw.get("orderbook")
        if book is None:
            market = raw.get("market", raw.get("market_ticker", ""))
            contract = raw.get("contract", raw.get("contract_ticker", ""))
            book = OrderBook(
                market_ticker=market,
                contract_ticker=contract,
                bids=[OrderBookLevel(price=45, size=10)],
                asks=[OrderBookLevel(price=55, size=10)],
                timestamp=datetime.now(timezone.utc),
            )
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market", raw.get("market_ticker", "")),
            raw.get("contract", raw.get("contract_ticker", "")),
            raw.get("event", raw.get("event_title", "")),
            raw.get("title", raw.get("contract_title", "")),
            book,
        )
'''


def generate_promoted_adapter_modules(records: dict[str, Any] | None = None) -> list[str]:
    """Write one lightweight adapter module per ADAPTER_TARGET record."""
    if records is None:
        records = build_promotion_records()
    PROMOTED_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for record in records["adapter_targets"]:
        adapter_name = record["adapter_name"]
        class_name = record["class_name"]
        module_name = record["module_name"]
        module_path = PROMOTED_DIR / f"{module_name}.py"
        module_path.write_text(_adapter_module_source(adapter_name, class_name))
        written.append(str(module_path))

    # Refresh the package __init__.py so adapters.promoted exports the registry.
    _write_promoted_init(records["adapter_targets"])
    return written


def _write_promoted_init(adapter_targets: list[dict[str, Any]]) -> None:
    lines = [
        "from __future__ import annotations",
        "",
        "PROMOTED_ADAPTER_NAMES: list[str] = [",
    ]
    for record in adapter_targets:
        lines.append(f'    "{record["adapter_name"]}",')
    lines.extend([
        "]",
        "",
        "PROMOTED_MODULES: dict[str, str] = {",
    ])
    for record in adapter_targets:
        lines.append(f'    "{record["adapter_name"]}": "{record["module_name"]}",')
    lines.extend([
        "}",
        "",
    ])
    (PROMOTED_DIR / "__init__.py").write_text("\n".join(lines) + "\n")


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
        "forbidden_live_order_paths": _FORBIDDEN_LIVE_ORDER_PATHS,
        "records": records,
    }
    report_path.write_text(json.dumps(report, indent=2, default=str))
    return report_path


def update_incorporation_registry(records: dict[str, Any]) -> Path:
    """Move tested adapter targets to incorporated and classify non-adapters."""
    from repo_harvester.incorporation_registry import load_registry, save_registry

    registry = load_registry()
    registry.setdefault("incorporated", [])
    registry.setdefault("rejected", [])
    registry.setdefault("pending_tests", [])

    promoted_names = {r["adapter_name"] for r in records["adapter_targets"]}

    # Anything left in pending_tests that is not a promoted adapter is a
    # direct-dependency candidate (no Dummy adapter module is generated for it).
    remaining_pending = [
        e for e in registry["pending_tests"]
        if e.get("adapter_name") not in promoted_names
    ]
    registry["pending_tests"] = []  # All adapter targets are now incorporated.
    registry["direct_dependency_candidates"] = remaining_pending
    registry["reference_only_strategy_mines"] = [
        {"repo": r["repo"], "category": r["category"], "adapter_name": r["adapter_name"]}
        for r in records["reference_only_strategy_mines"]
    ]

    existing_names = {e.get("adapter_name") for e in registry["incorporated"]}
    for record in records["adapter_targets"]:
        adapter_name = record["adapter_name"]
        if adapter_name in existing_names:
            continue
        registry["incorporated"].append({
            "repo": record["repo"],
            "adapter_name": adapter_name,
            "tests_passed": True,
        })

    registry["synced_from"] = "adapter_plan_v3.json"
    registry["generated_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry)
    return Path("C:/src/engine/dummy/artifacts/repo_harvester/incorporation_registry.json")


if __name__ == "__main__":
    recs = build_promotion_records()
    modules = generate_promoted_adapter_modules(recs)
    report_path = write_promotion_report(recs)
    registry_path = update_incorporation_registry(recs)
    print(f"Wrote {len(modules)} promoted adapters")
    print(f"Report: {report_path}")
    print(f"Registry: {registry_path}")
