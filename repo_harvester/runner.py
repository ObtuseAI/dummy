import json
import asyncio
from pathlib import Path
from repo_harvester.manifest import ALL_REPOS_V2, REPOS_V2
from repo_harvester.auditor import audit_repo
from core.ontology import RepoVerdict

OUT = Path("C:/src/engine/dumby/artifacts/repo_harvester")
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
