import json
import asyncio
from pathlib import Path
from repo_harvester.manifest import ALL_REPOS_V2, REPOS_V2
from repo_harvester.auditor import audit_repo
from repo_harvester.adapter_planner import generate_adapter_plan
from core.ontology import RepoVerdict

OUT = Path("C:/src/engine/dummy/artifacts/repo_harvester")
OUT.mkdir(parents=True, exist_ok=True)

SEM = asyncio.Semaphore(5)

CATEGORY_REPORTS = {
    "sports_prediction_odds": "sports_repo_report.json",
    "weather_prediction_market": "weather_repo_report.json",
    "stocks_equities_options_macro": "stocks_repo_report.json",
    "commodities_energy_agriculture": "commodities_repo_report.json",
    "crypto_btc_event_market": "crypto_repo_report.json",
    "kalshi_polymarket_arbitrage": "prediction_market_repo_report.json",
    "prediction_market_native": "prediction_market_repo_report.json",
}


def _category_display_name(slug: str) -> str:
    for group in REPOS_V2:
        if group["category"] == slug:
            return group["display_name"]
    return slug


async def _audit_one(owner: str, name: str, category: str) -> dict:
    async with SEM:
        try:
            return await audit_repo(owner, name, category=category)
        except Exception as e:
            return {
                "owner": owner,
                "name": name,
                "category": category,
                "url": f"https://github.com/{owner}/{name}",
                "error": str(e),
                "verdict": RepoVerdict.REJECT_BROKEN.value,
                "verdict_reasons": [f"Audit failed: {e}"],
            }


def _build_adapter_plan(results: list[dict]) -> list[dict]:
    """Generate metadata-level adapter plans for direct-dependency / adapter-target candidates."""
    plans = []
    for r in results:
        verdict = r.get("verdict")
        if verdict in (RepoVerdict.DIRECT_DEPENDENCY_CANDIDATE.value, RepoVerdict.ADAPTER_TARGET.value):
            plans.append({
                "repo": f"{r['owner']}/{r['name']}",
                "category": r.get("category"),
                "adapter_name": f"{r['name']}_adapter",
                "emits_native_types": False,
                "notes": "Metadata-level plan; source review required before implementation.",
            })
    return plans


async def run_source_scan(owner: str, name: str) -> dict:
    from repo_harvester.source_scanner import scan_repo
    return await scan_repo(owner, name)


async def run_v2_with_source_scan(limit: int = 20):
    results = []
    scans = []
    plans = []
    for owner, name, category in ALL_REPOS_V2[:limit]:
        try:
            meta = await audit_repo(owner, name, category=category)
            scan = await run_source_scan(owner, name)
            plan = generate_adapter_plan(meta, scan)
            meta["scan"] = scan
            meta["adapter_plan"] = plan
            results.append(meta)
            scans.append(scan)
            plans.append(plan)
        except Exception as e:
            results.append({
                "owner": owner,
                "name": name,
                "category": category,
                "error": str(e),
                "verdict": RepoVerdict.REJECT_BROKEN.value,
            })

    # Adapter plan artifact (source-informed)
    (OUT / "adapter_plan_v2.json").write_text(json.dumps({
        "plan_count": len(plans),
        "plans": plans,
        "notes": f"Source-informed adapter plans for first {limit} repos in V2 manifest.",
    }, indent=2, default=str))

    # Firewall bypass scan report
    direct_order_repos = [s for s in scans if s.get("direct_order_hits")]
    secret_risk_repos = [s for s in scans if len(s.get("secret_hits", [])) > 5]
    (OUT / "firewall_bypass_scan_report.json").write_text(json.dumps({
        "status": "completed",
        "repos_scanned": len(scans),
        "direct_order_count": len(direct_order_repos),
        "direct_order_repos": direct_order_repos,
        "secret_risk_count": len(secret_risk_repos),
        "secret_risk_repos": secret_risk_repos,
        "notes": "Source-level firewall bypass scan. Rejects repos with direct order paths or excessive secret handling.",
    }, indent=2, default=str))

    return results


async def run_harvester():
    results = await asyncio.gather(
        *[_audit_one(owner, name, category) for owner, name, category in ALL_REPOS_V2]
    )

    manifest = [
        {"owner": r["owner"], "name": r["name"], "category": r.get("category"), "verdict": r["verdict"]}
        for r in results
    ]

    category_map = {}
    for r in results:
        cat = r.get("category")
        if cat:
            category_map.setdefault(cat, []).append({
                "owner": r["owner"],
                "name": r["name"],
                "verdict": r["verdict"],
            })

    classification_counts = {}
    for r in results:
        classification_counts[r["verdict"]] = classification_counts.get(r["verdict"], 0) + 1

    rejected = [r for r in results if str(r.get("verdict", "")).startswith("REJECT")]

    # Core V2 artifacts
    (OUT / "repo_manifest_v2.json").write_text(json.dumps(manifest, indent=2, default=str))
    (OUT / "repo_classification_v2.json").write_text(
        json.dumps({"counts": classification_counts, "results": results}, indent=2, default=str)
    )
    (OUT / "category_map_v2.json").write_text(
        json.dumps({"category_map": category_map, "display_names": {g["category"]: g["display_name"] for g in REPOS_V2}}, indent=2, default=str)
    )

    # Per-category reports
    for slug, filename in CATEGORY_REPORTS.items():
        report = {
            "category": slug,
            "display_name": _category_display_name(slug),
            "repos": [r for r in results if r.get("category") == slug],
        }
        (OUT / filename).write_text(json.dumps(report, indent=2, default=str))

    # Rejected repo report
    (OUT / "rejected_repo_report.json").write_text(json.dumps({
        "rejected_count": len(rejected),
        "rejected": rejected,
    }, indent=2, default=str))

    # Adapter plan (metadata-level)
    (OUT / "adapter_plan_v2.json").write_text(json.dumps({
        "plan_count": 0,
        "plans": _build_adapter_plan(results),
        "notes": "Metadata-only scan; concrete adapter plans require source review.",
    }, indent=2, default=str))

    # Firewall bypass scan placeholder
    (OUT / "firewall_bypass_scan_report.json").write_text(json.dumps({
        "status": "pending",
        "notes": "Source scan pending; no static or live firewall-bypass analysis performed at metadata level.",
    }, indent=2))

    return results


if __name__ == "__main__":
    asyncio.run(run_harvester())
