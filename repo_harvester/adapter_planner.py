from datetime import datetime, timezone, timedelta
from core.ontology import RepoVerdict
from repo_harvester.retry_policy import PENDING_RETRY, PENDING_REVIEW

PERMISSIVE_LICENSES = {
    "MIT", "Apache-2.0", "Apache-2", "BSD-2-Clause", "BSD-3-Clause",
    "ISC", "Unlicense", "0BSD", "WTFPL",
}

DIRECT_DEPENDENCY_CATEGORIES = {
    "universal_ml_forecasting_optimization",
    "financial_data_market_data",
    "dashboard_api_observability",
}

DATA_ONLY_CATEGORIES = {
    "weather_prediction_market",
    "commodities_energy_agriculture",
}

MODEL_ZOO_CATEGORY = "universal_ml_forecasting_optimization"


def _is_stale(pushed_at: str | None) -> bool:
    if not pushed_at:
        return True
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - pushed > timedelta(days=730)
    except Exception:
        return True


def generate_adapter_plan(repo_meta: dict, scan: dict) -> dict:
    owner, name = repo_meta["owner"], repo_meta["name"]
    full = f"{owner}/{name}"
    if scan["direct_order_hits"]:
        verdict = RepoVerdict.REJECT_DIRECT_ORDER_BYPASS
        plans = []
    elif scan["secret_hits"] and len(scan["secret_hits"]) > 5:
        verdict = RepoVerdict.REJECT_SECRET_RISK
        plans = []
    elif repo_meta.get("license") in ["MIT", "Apache-2.0"]:
        verdict = RepoVerdict.ADAPTER_TARGET if (scan["strategy_hits"] or scan["forecast_hits"]) else RepoVerdict.REFERENCE_MINE
        plans = [{
            "repo": full,
            "adapter_name": f"{name.replace('-', '_')}_adapter",
            "emits_native_types": False,
            "integration_status": "pending",
            "integration_kind": "scaffold_only",
            "upstream_integration_verified": False,
            "production_capability": False,
            "notes": f"Strategy hits: {len(scan['strategy_hits'])}, forecast hits: {len(scan['forecast_hits'])}, risk hits: {len(scan['risk_hits'])}",
        }] if verdict == RepoVerdict.ADAPTER_TARGET else []
    else:
        verdict = RepoVerdict.REFERENCE_MINE
        plans = []
    return {"repo": full, "verdict": verdict.value, "plans": plans, "scan_summary": scan}


def classify_repo_source(repo_meta: dict, scan: dict, category: str | None = None) -> tuple[RepoVerdict, list[str]]:
    """Source-aware classification that separates dependency, adapter, reference, and rejection bins."""
    reasons: list[str] = []
    license_id = repo_meta.get("license")
    pushed_at = repo_meta.get("pushed_at")
    description = (repo_meta.get("description") or "").lower()

    direct_order_hits = scan.get("direct_order_hits", []) or scan.get("kalshi_order_hits", []) or scan.get("polymarket_order_hits", [])
    private_key_hits = scan.get("private_key_hits", [])
    api_secret_hits = scan.get("api_secret_hits", [])
    secret_hits = scan.get("secret_hits", []) or private_key_hits or api_secret_hits

    if direct_order_hits:
        reasons.append(f"Direct order placement code detected in {len(direct_order_hits)} file(s)")
        return RepoVerdict.REJECT_DIRECT_ORDER_BYPASS, reasons

    if private_key_hits:
        reasons.append(f"Private key handling detected in {len(private_key_hits)} file(s)")
        return RepoVerdict.REJECT_SECRET_RISK, reasons

    if len(api_secret_hits) > 3 or len(secret_hits) > 5:
        reasons.append(f"Excessive API secret handling detected ({len(api_secret_hits)} api_secret, {len(secret_hits)} total secret)")
        return RepoVerdict.REJECT_SECRET_RISK, reasons

    if category == "sports_prediction_odds" and any(kw in description for kw in ["scraping", "bookmaker", "bookmakers", "scrape"]):
        reasons.append("Sports repo description mentions scraping/bookmaker")
        return RepoVerdict.REJECT_SCRAPING_RISK, reasons

    if not license_id or license_id in ["NOASSERTION", "NONE"]:
        reasons.append("No OSI license")
        return RepoVerdict.REJECT_LICENSE, reasons

    if license_id not in PERMISSIVE_LICENSES:
        reasons.append(f"License {license_id} is not in the permissive allowlist")
        return RepoVerdict.REJECT_LICENSE, reasons

    if _is_stale(pushed_at):
        reasons.append("Repo stale > 2 years")
        return RepoVerdict.REJECT_STALE, reasons

    if category == MODEL_ZOO_CATEGORY:
        reasons.append(
            "General model/optimization library is a dependency candidate; "
            "a pass-through shell is not an adapter integration"
        )
        return RepoVerdict.DIRECT_DEPENDENCY_CANDIDATE, reasons

    # Stable upstream libraries that provide no trading logic become direct dependencies.
    logic_categories = [
        "strategy", "forecast", "risk", "arbitrage", "websocket", "settlement",
        "dashboard", "sports", "weather", "stocks", "commodities", "crypto",
    ]
    useful_logic = any(scan.get(f"{k}_hits", []) for k in logic_categories)
    if category in DIRECT_DEPENDENCY_CATEGORIES and not useful_logic:
        reasons.append("Stable upstream library in dependency category with no trading/order logic")
        return RepoVerdict.DIRECT_DEPENDENCY_CANDIDATE, reasons

    if useful_logic:
        detected = ", ".join(k for k in logic_categories if scan.get(f"{k}_hits"))
        reasons.append(f"Source contains useful logic suitable for adapter wrapping: {detected}")
        return RepoVerdict.ADAPTER_TARGET, reasons

    reasons.append("Permissive license; safe reference mine")
    return RepoVerdict.REFERENCE_MINE, reasons


def generate_adapter_plan_v3(repo_meta: dict, scan: dict, category: str | None = None) -> dict:
    owner = repo_meta.get("owner", "")
    name = repo_meta.get("name", "")
    full = f"{owner}/{name}"
    harvest_status = scan.get("harvest_status")
    if harvest_status == "FAILED_PERMANENT":
        return {
            "repo": full,
            "category": category,
            "verdict": RepoVerdict.REJECT_BROKEN.value,
            "verdict_reasons": ["Repository was not found after a definitive 404 response"],
            "plans": [],
            "scan_summary": {
                "files_scanned": 0,
                "files_considered": 0,
                "tree_size": 0,
                "harvest_status": harvest_status,
                "scan_complete": False,
                "error": scan.get("error"),
            },
        }
    if harvest_status in {PENDING_RETRY, PENDING_REVIEW} or scan.get("scan_complete") is False:
        pending_status = PENDING_RETRY if harvest_status == PENDING_RETRY else PENDING_REVIEW
        return {
            "repo": full,
            "category": category,
            "verdict": pending_status,
            "verdict_reasons": [
                "Source evidence is incomplete; repository remains pending and cannot be incorporated"
            ],
            "plans": [],
            "scan_summary": {
                "files_scanned": scan.get("files_scanned", 0),
                "files_considered": scan.get("files_considered", 0),
                "tree_size": scan.get("tree_size", 0),
                "harvest_status": harvest_status or PENDING_REVIEW,
                "scan_complete": False,
                "error": scan.get("error"),
            },
        }

    verdict, reasons = classify_repo_source(repo_meta, scan, category=category)

    plans = []
    if verdict == RepoVerdict.DIRECT_DEPENDENCY_CANDIDATE:
        plans.append({
            "repo": full,
            "adapter_name": f"{name.replace('-', '_')}_dependency",
            "plan_type": "DIRECT_DEPENDENCY_CANDIDATE",
            "emits_native_types": False,
            "integration_status": "pending_dependency_review",
            "production_capability": False,
            "notes": "Add to project dependencies; no adapter wrapper required.",
        })
    elif verdict == RepoVerdict.ADAPTER_TARGET:
        logic_categories = [
            "strategy", "forecast", "risk", "arbitrage", "websocket", "settlement",
            "dashboard", "sports", "weather", "stocks", "commodities", "crypto",
        ]
        detected = [k for k in logic_categories if scan.get(f"{k}_hits")]
        plans.append({
            "repo": full,
            "adapter_name": f"{name.replace('-', '_')}_adapter",
            "plan_type": "ADAPTER_TARGET",
            "emits_native_types": False,
            "integration_status": "pending",
            "integration_kind": "scaffold_only",
            "upstream_integration_verified": False,
            "test_status": "pending_adapter_specific_tests",
            "production_capability": False,
            "prediction_authority": False,
            "execution_authority": False,
            "data_only": category in DATA_ONLY_CATEGORIES,
            "passthrough_model_zoo": category == MODEL_ZOO_CATEGORY,
            "notes": f"Wrap source logic into Dummy-native types. Detected categories: {', '.join(detected)}.",
        })

    scan_summary_keys = [
        "direct_order", "kalshi_order", "polymarket_order", "private_key", "api_secret",
        "strategy", "forecast", "risk", "arbitrage", "websocket", "settlement", "dashboard",
        "sports", "weather", "stocks", "commodities", "crypto",
    ]
    scan_summary = {
        "files_scanned": scan.get("files_scanned", 0),
        "files_considered": scan.get("files_considered", 0),
        "tree_size": scan.get("tree_size", 0),
        "harvest_status": scan.get("harvest_status", "COMPLETE"),
        "scan_complete": scan.get("scan_complete", True),
    }
    for key in scan_summary_keys:
        scan_summary[f"{key}_hits"] = scan.get(f"{key}_hits", [])

    return {
        "repo": full,
        "category": category,
        "verdict": verdict.value,
        "verdict_reasons": reasons,
        "plans": plans,
        "scan_summary": scan_summary,
    }
