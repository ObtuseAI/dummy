"""V2 source-scan digestion pipeline.

Produces:
- artifacts/repo_harvester/source_scan_summary_v1.json
- artifacts/repo_harvester/firewall_bypass_scan_report_v1.json
- artifacts/repo_harvester/adapter_plan_v3.json
- artifacts/repo_harvester/rejected_repo_report_v3.json
- artifacts/repo_harvester/strategy_extraction_report_v1.json
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from repo_harvester.manifest import ALL_REPOS_V2, REPOS_V2
from repo_harvester.source_scanner import SCAN_CATEGORIES, categorize_text, scan_text
from repo_harvester.adapter_planner import classify_repo_source, generate_adapter_plan_v3
from core.ontology import RepoVerdict

OUT = Path("C:/src/engine/dummy/artifacts/repo_harvester")
CACHE = OUT / "source_scan_cache_v1"
CACHE.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN is required. Set it in .env or export it from your secret manager (e.g. `gh auth token`).")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}
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
                return data
        except Exception:
            pass
    return None


def _save_cache(owner: str, name: str, data: dict):
    cp = _cache_path(owner, name)
    data["version"] = 1
    cp.write_text(json.dumps(data, indent=2, default=str))


async def _sleep_until(reset_ts: int):
    now = datetime.now(timezone.utc).timestamp()
    wait = max(1, reset_ts - int(now) + 2)
    print(f"Rate limit hit; sleeping {wait}s until reset")
    await asyncio.sleep(wait)


async def _github_get(client: httpx.AsyncClient, url: str) -> dict:
    while True:
        r = await client.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
        remaining = r.headers.get("x-ratelimit-remaining")
        reset = r.headers.get("x-ratelimit-reset")
        if r.status_code in (403, 429) and remaining == "0" and reset:
            await _sleep_until(int(reset))
            continue
        if r.status_code == 404:
            raise FileNotFoundError(url)
        r.raise_for_status()
        return r.json()


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
        result = {"owner": owner, "name": name, "category": category, "error": "repo_not_found", "files_scanned": 0}
        _save_cache(owner, name, {"meta": None, "scan": result})
        return result
    except Exception as e:
        result = {"owner": owner, "name": name, "category": category, "error": str(e), "files_scanned": 0}
        _save_cache(owner, name, {"meta": None, "scan": result})
        return result

    repo_size_kb = meta.get("size", 0)
    # For very large upstream libraries, avoid giant recursive trees and only scan root files.
    use_recursive = repo_size_kb < 20_000

    try:
        tree = await fetch_repo_tree(client, owner, name, recursive=use_recursive)
    except Exception as e:
        result = {"owner": owner, "name": name, "category": category, "error": f"tree_fetch_failed: {e}", "files_scanned": 0}
        _save_cache(owner, name, {"meta": meta, "scan": result})
        return result

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
    }
    for cat in SCAN_CATEGORIES:
        result[f"{cat}_hits"] = []

    for f in files:
        try:
            text = await fetch_file(client, owner, name, f["path"])
        except Exception:
            continue
        result["files_scanned"] += 1
        categories = categorize_text(text)
        for cat, hits in categories.items():
            if hits:
                result[f"{cat}_hits"].append(f["path"])

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
        "repos_scanned": len(results),
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
        "status": "completed",
        "repos_scanned": len(plans),
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

    # Strategy extraction report.
    strategy_report = build_strategy_extraction_report(plans)
    (OUT / "strategy_extraction_report_v1.json").write_text(json.dumps(strategy_report, indent=2, default=str))

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
    """Build Dummy-native strategy candidates from repo-derived ADAPTER_TARGET plans.

    Every candidate emits TradeProposal objects only and never calls live order endpoints.
    """
    candidates = []

    def add(repo: str, category: str, strategy_name: str, description: str, market_types: list[str]):
        candidates.append({
            "repo": repo,
            "source_category": category,
            "strategy_name": strategy_name,
            "description": description,
            "market_types": market_types,
            "output": "TradeProposal",
            "calls_live_order_endpoints": False,
        })

    for plan in plans:
        if plan["verdict"] != RepoVerdict.ADAPTER_TARGET.value:
            continue
        repo = plan["repo"]
        category = plan["category"]
        scan = plan["scan_summary"]
        if scan.get("weather_hits"):
            add(repo, category, "KalshiWeatherForecastStrategy",
                "Combine NOAA/open-meteo forecasts with Kalshi weather contract orderbooks; emit TradeProposal when model probability diverges from market.",
                ["weather"])
        if scan.get("sports_hits"):
            add(repo, category, "SportsMomentumStrategy",
                "Mine repo odds/forecast logic for momentum and mispricing signals; emit TradeProposal for sports event contracts only.",
                ["sports"])
        if scan.get("crypto_hits") or "btc" in repo.lower() or "crypto" in repo.lower():
            add(repo, category, "CryptoEventMarketStrategy",
                "Convert repo BTC/crypto event market signals into Dummy-native TradeProposal objects without touching exchange order endpoints.",
                ["crypto", "btc", "event"])
        if scan.get("stocks_hits"):
            add(repo, category, "StockMacroMomentumStrategy",
                "Use repo stock/index/macro forecasting patterns to generate TradeProposal objects for relevant Kalshi macro contracts.",
                ["stocks", "indices", "macro"])
        if scan.get("commodities_hits"):
            add(repo, category, "CommoditiesEnergyStrategy",
                "Apply commodities/energy price-forecast logic to Kalshi energy contracts; output TradeProposal only.",
                ["commodities", "energy"])
        if scan.get("arbitrage_hits"):
            add(repo, category, "RepoDerivedCrossMarketArbitrage",
                "Identify price disagreements across prediction markets using repo arbitrage patterns and emit paired TradeProposal legs.",
                ["cross_market", "arbitrage"])
        if scan.get("strategy_hits") and scan.get("websocket_hits"):
            add(repo, category, "OrderbookSpreadCaptureStrategy",
                "Watch orderbook updates via WebSocket logic mined from repos and emit TradeProposal when spread capture meets caps.",
                ["orderbook", "spread"])
        if scan.get("settlement_hits") or scan.get("forecast_hits"):
            add(repo, category, "StaleQuoteDetectionStrategy",
                "Detect stale quotes near settlement/expiration using repo forecast/settlement patterns and emit TradeProposal only.",
                ["stale_quote", "settlement"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "notes": "All repo-derived strategy candidates emit Dummy-native TradeProposal objects and are prohibited from calling live order endpoints.",
    }


if __name__ == "__main__":
    print("Starting V2 source-scan digestion...")
    reports = asyncio.run(run_v2_digestion())
    print("Done.")
    print(json.dumps({k: len(str(v)) for k, v in reports.items()}, indent=2))
