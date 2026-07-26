"""V2 source-scan digestion pipeline.

Produces:
- artifacts/repo_harvester/source_scan_summary_v1.json
- artifacts/repo_harvester/firewall_bypass_scan_report_v1.json
- artifacts/repo_harvester/adapter_plan_v3.json
- artifacts/repo_harvester/rejected_repo_report_v3.json
- artifacts/repo_harvester/strategy_extraction_report_v2.json (keyword-template
  INVENTORY; it extracts no strategy logic -- see
  ``build_strategy_extraction_report``)
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from repo_harvester.manifest import ALL_REPOS_V2
from repo_harvester.source_scanner import SCAN_CATEGORIES, categorize_text
from repo_harvester.adapter_planner import generate_adapter_plan_v3
from core.ontology import RepoVerdict
from repo_harvester.adapter_planner import DATA_ONLY_CATEGORIES
from repo_harvester.strategy_catalog import (
    KEYWORD_TEMPLATE_DERIVATION,
    KEYWORD_TEMPLATE_EXTRACTION_METHOD,
    STRATEGY_CATALOG_FILENAME,
    STRATEGY_REPORT_SCHEMA_VERSION,
)
from repo_harvester.retry_policy import (
    HarvestRetryExhausted,
    PENDING_RETRY,
    PENDING_REVIEW,
    run_with_bounded_retry,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "artifacts" / "repo_harvester"
CACHE = OUT / "source_scan_cache_v1"
CACHE.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github+json",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"
SEM = asyncio.Semaphore(8)
MAX_FILES_PER_REPO = 30
MAX_TREE_SIZE_FOR_RECURSIVE = 3000
HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _cache_path(owner: str, name: str) -> Path:
    safe = f"{owner}_{name}".replace("/", "_")
    return CACHE / f"{safe}.json"


def _load_cache(owner: str, name: str) -> dict | None:
    cp = _cache_path(owner, name)
    if cp.exists():
        try:
            data = json.loads(cp.read_text())
            if data.get("version") == 1:
                scan = data.get("scan")
                if not isinstance(scan, dict):
                    return None
                status = scan.get("harvest_status")
                # Old complete cache entries had no explicit status. Error
                # cache entries are deliberately ignored so an outage cannot
                # become a permanent pseudo-result.
                if status in {"COMPLETE", "FAILED_PERMANENT"}:
                    return data
                if status is None and not scan.get("error"):
                    return data
        except Exception:
            pass
    return None


def _save_cache(owner: str, name: str, data: dict):
    cp = _cache_path(owner, name)
    data["version"] = 1
    cp.write_text(json.dumps(data, indent=2, default=str))


async def _github_get(client: httpx.AsyncClient, url: str) -> dict:
    async def _request() -> dict:
        r = await client.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
        if r.status_code == 404:
            raise FileNotFoundError(url)
        r.raise_for_status()
        return r.json()

    return await run_with_bounded_retry(_request)


async def fetch_repo_metadata(client: httpx.AsyncClient, owner: str, name: str) -> dict:
    return await _github_get(client, f"https://api.github.com/repos/{owner}/{name}")


async def fetch_repo_tree(client: httpx.AsyncClient, owner: str, name: str, sha: str = "HEAD", recursive: bool = True) -> dict:
    url = f"https://api.github.com/repos/{owner}/{name}/git/trees/{sha}"
    if recursive:
        url += "?recursive=1"
    return await _github_get(client, url)


async def fetch_file(client: httpx.AsyncClient, owner: str, name: str, path: str, ref: str = "HEAD") -> str:
    data = await _github_get(client, f"https://api.github.com/repos/{owner}/{name}/contents/{path}?ref={ref}")
    import base64
    if isinstance(data, dict) and data.get("content"):
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    return ""


def _skip_path(path: str) -> bool:
    lowered = path.lower()
    skip = [
        "node_modules", "vendor", "dist", "build", ".git", "__pycache__",
        "test_", "_test.", ".test.", "/tests/", "/docs/", "/examples/",
    ]
    return any(fragment in lowered for fragment in skip)


def _score_file(path: str) -> int:
    path_lower = path.lower()
    score = 0
    if any(path.endswith(ext) for ext in (".py", ".rs", ".go", ".sol")):
        score += 20
    if any(path.endswith(ext) for ext in (".ts", ".js", ".jsx", ".tsx")):
        score += 10
    if "/src/" in path_lower or path.count("/") <= 1:
        score += 15
    if any(k in path_lower for k in ("main", "app", "cli", "bot", "strategy")):
        score += 10
    if any(k in path_lower for k in ("test", "doc", "example", "benchmark", "fixture")):
        score -= 20
    return score


SCAN_EXTENSIONS = (".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".sol", ".java")


async def _scan_one_repo(client: httpx.AsyncClient, owner: str, name: str, category: str) -> dict[str, Any]:
    cached = _load_cache(owner, name)
    if cached and cached.get("scan"):
        return cached["scan"]

    try:
        meta = await fetch_repo_metadata(client, owner, name)
    except FileNotFoundError:
        result = {
            "owner": owner,
            "name": name,
            "category": category,
            "error": "repo_not_found",
            "files_scanned": 0,
            "scan_complete": False,
            "harvest_status": "FAILED_PERMANENT",
            "retryable": False,
        }
        _save_cache(owner, name, {"meta": None, "scan": result})
        return result
    except HarvestRetryExhausted as exc:
        return {
            "owner": owner,
            "name": name,
            "category": category,
            "error": f"{type(exc.cause).__name__}: {exc.cause}",
            "files_scanned": 0,
            "scan_complete": False,
            "harvest_status": PENDING_RETRY,
            "retryable": True,
            "retry_attempts": exc.attempts,
        }
    except Exception as e:
        return {
            "owner": owner,
            "name": name,
            "category": category,
            "error": f"{type(e).__name__}: {e}",
            "files_scanned": 0,
            "scan_complete": False,
            "harvest_status": PENDING_REVIEW,
            "retryable": False,
        }

    repo_size_kb = meta.get("size", 0)
    # For very large upstream libraries, avoid giant recursive trees and only scan root files.
    use_recursive = repo_size_kb < 20_000

    try:
        tree = await fetch_repo_tree(client, owner, name, recursive=use_recursive)
    except HarvestRetryExhausted as exc:
        return {
            "owner": owner,
            "name": name,
            "category": category,
            "error": f"tree_fetch_failed: {type(exc.cause).__name__}: {exc.cause}",
            "files_scanned": 0,
            "scan_complete": False,
            "harvest_status": PENDING_RETRY,
            "retryable": True,
            "retry_attempts": exc.attempts,
        }
    except Exception as e:
        return {
            "owner": owner,
            "name": name,
            "category": category,
            "error": f"tree_fetch_failed: {type(e).__name__}: {e}",
            "files_scanned": 0,
            "scan_complete": False,
            "harvest_status": PENDING_REVIEW,
            "retryable": False,
        }

    files = [
        t for t in tree.get("tree", [])
        if t.get("type") == "blob" and t.get("path", "").endswith(SCAN_EXTENSIONS)
    ]
    files = [f for f in files if not _skip_path(f["path"])]
    files = sorted(files, key=lambda f: (f.get("size", 0), -_score_file(f["path"])))[:MAX_FILES_PER_REPO]

    result = {
        "owner": owner,
        "name": name,
        "category": category,
        "files_scanned": 0,
        "files_considered": len(files),
        "tree_size": len(tree.get("tree", [])),
        "repo_size_kb": repo_size_kb,
        "file_fetch_failures": [],
    }
    for cat in SCAN_CATEGORIES:
        result[f"{cat}_hits"] = []

    for f in files:
        try:
            text = await fetch_file(client, owner, name, f["path"])
        except Exception as exc:
            result["file_fetch_failures"].append(
                {
                    "path": f["path"],
                    "error_type": type(exc).__name__,
                    "retryable": isinstance(exc, HarvestRetryExhausted),
                }
            )
            continue
        result["files_scanned"] += 1
        categories = categorize_text(text)
        for cat, hits in categories.items():
            if hits:
                result[f"{cat}_hits"].append(f["path"])

    result["file_fetch_failure_count"] = len(result["file_fetch_failures"])
    result["scan_complete"] = not result["file_fetch_failures"]
    all_failures_retryable = bool(result["file_fetch_failures"]) and all(
        failure["retryable"] for failure in result["file_fetch_failures"]
    )
    if result["scan_complete"]:
        result["harvest_status"] = "COMPLETE"
        result["retryable"] = False
    else:
        result["harvest_status"] = (
            PENDING_RETRY if all_failures_retryable else PENDING_REVIEW
        )
        result["retryable"] = all_failures_retryable
    if result["scan_complete"]:
        _save_cache(owner, name, {"meta": meta, "scan": result})
    return result


async def run_v2_digestion() -> dict[str, Any]:
    results: list[dict] = []
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        tasks = [
            _scan_one_repo(client, owner, name, category)
            for owner, name, category in ALL_REPOS_V2
        ]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            if len(results) % 20 == 0:
                print(f"Scanned {len(results)}/{len(ALL_REPOS_V2)} repos...")

    # Load metadata from cache for classification.
    plans = []
    rejected = []
    summaries = []
    total_files = 0

    for owner, name, category in ALL_REPOS_V2:
        cache = _load_cache(owner, name)
        meta = cache.get("meta") if cache else None
        scan = next((r for r in results if r["owner"] == owner and r["name"] == name), {"owner": owner, "name": name, "category": category, "files_scanned": 0})
        total_files += scan.get("files_scanned", 0)

        if not meta:
            repo_meta = {"owner": owner, "name": name, "license": None, "pushed_at": None, "description": ""}
        else:
            repo_meta = {
                "owner": owner,
                "name": name,
                "license": (meta.get("license") or {}).get("spdx_id"),
                "pushed_at": meta.get("pushed_at"),
                "description": meta.get("description", ""),
            }

        plan = generate_adapter_plan_v3(repo_meta, scan, category=category)
        plans.append(plan)
        summaries.append({
            "repo": f"{owner}/{name}",
            "category": category,
            "files_scanned": scan.get("files_scanned", 0),
            "tree_size": scan.get("tree_size", 0),
            "harvest_status": scan.get("harvest_status", "UNKNOWN"),
            "scan_complete": scan.get("scan_complete", False),
            "verdict": plan["verdict"],
        })
        if plan["verdict"].startswith("REJECT"):
            rejected.append(plan)

    # Source-scan summary.
    category_counts = {}
    verdict_counts = {}
    for plan in plans:
        category_counts.setdefault(plan["category"], {}).setdefault(plan["verdict"], 0)
        category_counts[plan["category"]][plan["verdict"]] += 1
        verdict_counts[plan["verdict"]] = verdict_counts.get(plan["verdict"], 0) + 1

    finding_totals = {cat: 0 for cat in SCAN_CATEGORIES}
    for plan in plans:
        for cat in SCAN_CATEGORIES:
            if plan["scan_summary"].get(f"{cat}_hits"):
                finding_totals[cat] += 1

    source_scan_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos_in_manifest": len(ALL_REPOS_V2),
        "repos_scanned": sum(r.get("scan_complete") is True for r in results),
        "repos_attempted": len(results),
        "pending_retry_count": sum(r.get("harvest_status") == PENDING_RETRY for r in results),
        "pending_review_count": sum(r.get("harvest_status") == PENDING_REVIEW for r in results),
        "total_files_scanned": total_files,
        "verdict_counts": verdict_counts,
        "category_verdict_counts": category_counts,
        "finding_category_repo_counts": finding_totals,
        "repo_summaries": summaries,
    }
    (OUT / "source_scan_summary_v1.json").write_text(json.dumps(source_scan_summary, indent=2, default=str))

    # Firewall bypass scan report.
    direct_order_repos = [
        p for p in plans
        if p["scan_summary"].get("direct_order_hits")
        or p["scan_summary"].get("kalshi_order_hits")
        or p["scan_summary"].get("polymarket_order_hits")
    ]
    secret_risk_repos = [
        p for p in plans
        if p["scan_summary"].get("private_key_hits")
        or len(p["scan_summary"].get("api_secret_hits", [])) > 3
        or len(p["scan_summary"].get("secret_hits", [])) > 5
    ]
    firewall_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "completed"
            if all(r.get("scan_complete") is True for r in results)
            else "partial_fail_closed_pending"
        ),
        "repos_scanned": sum(r.get("scan_complete") is True for r in results),
        "repos_attempted": len(results),
        "pending_repo_count": sum(r.get("scan_complete") is not True for r in results),
        "direct_order_count": len(direct_order_repos),
        "direct_order_repos": [{"repo": p["repo"], "category": p["category"], "hits": _bypass_hits(p)} for p in direct_order_repos],
        "secret_risk_count": len(secret_risk_repos),
        "secret_risk_repos": [{"repo": p["repo"], "category": p["category"], "hits": _secret_hits(p)} for p in secret_risk_repos],
        "notes": "Source-level firewall bypass scan. Repos with direct order paths or excessive secret handling are rejected.",
    }
    (OUT / "firewall_bypass_scan_report_v1.json").write_text(json.dumps(firewall_report, indent=2, default=str))

    # Adapter plan v3.
    accepted = [p for p in plans if p["verdict"] in (
        RepoVerdict.DIRECT_DEPENDENCY_CANDIDATE.value,
        RepoVerdict.ADAPTER_TARGET.value,
    )]
    adapter_plan_v3 = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_repos": len(plans),
        "accepted_count": len(accepted),
        "direct_dependency_count": len([p for p in plans if p["verdict"] == RepoVerdict.DIRECT_DEPENDENCY_CANDIDATE.value]),
        "adapter_target_count": len([p for p in plans if p["verdict"] == RepoVerdict.ADAPTER_TARGET.value]),
        "reference_mine_count": len([p for p in plans if p["verdict"] == RepoVerdict.REFERENCE_MINE.value]),
        "pending_retry_count": len([p for p in plans if p["verdict"] == PENDING_RETRY]),
        "pending_review_count": len([p for p in plans if p["verdict"] == PENDING_REVIEW]),
        "pending_repos": [
            {"repo": p["repo"], "category": p["category"], "verdict": p["verdict"]}
            for p in plans
            if p["verdict"] in {PENDING_RETRY, PENDING_REVIEW}
        ],
        "plans": accepted,
    }
    (OUT / "adapter_plan_v3.json").write_text(json.dumps(adapter_plan_v3, indent=2, default=str))

    # Rejected repo report v3.
    rejected_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rejected_count": len(rejected),
        "rejected": rejected,
    }
    (OUT / "rejected_repo_report_v3.json").write_text(json.dumps(rejected_report, indent=2, default=str))

    # Keyword-template inventory (NOT an extraction report -- see
    # build_strategy_extraction_report). Written under the v2 filename so the
    # catalog resolver prefers the labelled report over any stale v1 artifact.
    strategy_report = build_strategy_extraction_report(plans)
    (OUT / STRATEGY_CATALOG_FILENAME).write_text(json.dumps(strategy_report, indent=2, default=str))

    return {
        "source_scan_summary": source_scan_summary,
        "firewall_bypass_scan_report": firewall_report,
        "adapter_plan_v3": adapter_plan_v3,
        "rejected_repo_report": rejected_report,
        "strategy_extraction_report": strategy_report,
    }


def _bypass_hits(plan: dict) -> dict:
    return {
        "direct_order": plan["scan_summary"].get("direct_order_hits", []),
        "kalshi_order": plan["scan_summary"].get("kalshi_order_hits", []),
        "polymarket_order": plan["scan_summary"].get("polymarket_order_hits", []),
    }


def _secret_hits(plan: dict) -> dict:
    return {
        "private_key": plan["scan_summary"].get("private_key_hits", []),
        "api_secret": plan["scan_summary"].get("api_secret_hits", []),
    }


def build_strategy_extraction_report(plans: list[dict]) -> dict:
    """Build the harvester's keyword-template inventory for ADAPTER_TARGET plans.

    This function extracts NOTHING from a repository. A scan counter trips
    (``sports_hits``, ``crypto_hits``, ...) and a canned strategy name plus a
    canned description is emitted; no repo source is parsed, no threshold is
    read from a repo, and no module is generated. Presenting those emissions
    as "extracted strategy candidates" inflated a zero-extraction pipeline
    into a triple-digit headline (2026-07-24 external audit, section 6).

    The inventory is kept -- it truthfully records which repo tripped which
    keyword counter -- but it is labelled as template fan-out, carries no
    authority, and is reported separately from ``candidate_count``, which
    counts only genuinely repo-derived candidates. That count stays 0 until a
    real extraction-and-verification path is staffed.
    """
    repo_derived_candidates: list[dict] = []
    keyword_template_inventory = []
    data_only_inputs = []
    quarantined_candidates = []

    def add(
        repo: str,
        category: str,
        strategy_name: str,
        description: str,
        market_types: list[str],
        keyword_trigger: str,
    ):
        keyword_template_inventory.append({
            "repo": repo,
            "source_category": category,
            "strategy_name": strategy_name,
            "description": description,
            "market_types": market_types,
            # Inventory only: no module is generated for this row, so it
            # cannot emit anything.
            "output": "ABSTAIN",
            "calls_live_order_endpoints": False,
            "derivation": KEYWORD_TEMPLATE_DERIVATION,
            "repo_derived_logic": False,
            "extraction_method": KEYWORD_TEMPLATE_EXTRACTION_METHOD,
            "keyword_trigger": keyword_trigger,
            "description_is_canned_template": True,
            "inventory_role": "keyword_template_inventory",
            "prediction_authority": False,
            "trade_proposal_authority": False,
            "execution_authority": False,
        })

    for plan in plans:
        if plan["verdict"] != RepoVerdict.ADAPTER_TARGET.value:
            continue
        repo = plan["repo"]
        category = plan["category"]
        scan = plan["scan_summary"]
        if category in DATA_ONLY_CATEGORIES:
            data_only_inputs.append({
                "repo": repo,
                "source_category": category,
                "output": "RawObservation",
                "prediction_authority": False,
                "trade_proposal_authority": False,
                "execution_authority": False,
                "notes": "Weather and commodities are retained only as timestamped data inputs.",
            })
            continue
        if scan.get("sports_hits"):
            add(repo, category, "SportsMomentumStrategy",
                "Template: a sports keyword counter tripped in this repo. No repo logic was read.",
                ["sports"], "sports_hits")
        if scan.get("crypto_hits") or "btc" in repo.lower() or "crypto" in repo.lower():
            add(repo, category, "CryptoEventMarketStrategy",
                "Template: a crypto keyword counter (or the repo name) tripped. No repo logic was read.",
                ["crypto", "btc", "event"], "crypto_hits_or_repo_name")
        if scan.get("stocks_hits"):
            quarantined_candidates.append({
                "repo": repo,
                "source_category": category,
                "strategy_name": "StockMacroMomentumStrategy",
                "description": (
                    "Excluded research inventory: this market type is outside "
                    "the active prediction surface."
                ),
                "market_types": ["stocks", "indices", "macro"],
                "output": "ABSTAIN",
                "derivation": KEYWORD_TEMPLATE_DERIVATION,
                "repo_derived_logic": False,
                "keyword_trigger": "stocks_hits",
                "prediction_authority": False,
                "trade_proposal_authority": False,
                "execution_authority": False,
                "quarantine_reason": "outside_supported_prediction_targets",
            })
        if scan.get("arbitrage_hits"):
            add(repo, category, "RepoDerivedCrossMarketArbitrage",
                "Template: an arbitrage keyword counter tripped in this repo. No repo logic was read.",
                ["cross_market", "arbitrage"], "arbitrage_hits")
        if scan.get("strategy_hits") and scan.get("websocket_hits"):
            add(repo, category, "OrderbookSpreadCaptureStrategy",
                "Template: strategy and websocket keyword counters both tripped. No repo logic was read.",
                ["orderbook", "spread"], "strategy_hits_and_websocket_hits")
        if scan.get("settlement_hits") or scan.get("forecast_hits"):
            add(repo, category, "StaleQuoteDetectionStrategy",
                "Template: a settlement or forecast keyword counter tripped. No repo logic was read.",
                ["stale_quote", "settlement"], "settlement_hits_or_forecast_hits")

    return {
        "schema_version": STRATEGY_REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": KEYWORD_TEMPLATE_EXTRACTION_METHOD,
        "inventory_only": True,
        "repo_derived_extraction_implemented": False,
        # Headline: genuinely repo-derived, extracted candidates. There is no
        # extraction path, so this is 0 by construction, not by filtering.
        "candidate_count": len(repo_derived_candidates),
        "candidates": repo_derived_candidates,
        "repo_derived_candidate_count": len(repo_derived_candidates),
        "keyword_template_inventory_count": len(keyword_template_inventory),
        "keyword_template_inventory": keyword_template_inventory,
        "data_only_input_count": len(data_only_inputs),
        "data_only_inputs": data_only_inputs,
        "quarantined_candidate_count": len(quarantined_candidates),
        "quarantined_candidates": quarantined_candidates,
        "count_semantics": (
            "candidate_count counts repo-derived extracted strategies only. "
            "keyword_template_inventory_count counts rows emitted because a "
            "keyword counter tripped; those are inventory, not extractions, "
            "and must never be reported as extracted strategy candidates."
        ),
        "notes": (
            "The harvester is INVENTORY-ONLY: it records which repos tripped "
            "which keyword counters and never derives strategy logic from repo "
            "source. No inventory row carries prediction, trade-proposal or "
            "execution authority, and none generates a module. Weather and "
            "commodities are data-only. Other unsupported market categories "
            "remain excluded from prediction and execution."
        ),
    }


if __name__ == "__main__":
    print("Starting V2 source-scan digestion...")
    reports = asyncio.run(run_v2_digestion())
    print("Done.")
    print(json.dumps({k: len(str(v)) for k, v in reports.items()}, indent=2))
