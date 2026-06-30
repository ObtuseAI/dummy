import json, asyncio
from pathlib import Path
from repo_harvester.manifest import MANDATORY_REPOS
from repo_harvester.auditor import audit_repo

OUT = Path("C:/src/engine/dumby/artifacts/repo_harvester")
OUT.mkdir(parents=True, exist_ok=True)

async def run_harvester():
    results = []
    for owner, name in MANDATORY_REPOS:
        try:
            results.append(await audit_repo(owner, name))
        except Exception as e:
            results.append({"owner": owner, "name": name, "error": str(e), "verdict": "REJECT_BROKEN"})

    manifest = [{"owner": r["owner"], "name": r["name"], "verdict": r["verdict"]} for r in results]
    classes = {}
    for r in results:
        classes[r["verdict"]] = classes.get(r["verdict"], 0) + 1

    (OUT / "repo_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (OUT / "repo_scores.json").write_text(json.dumps(results, indent=2, default=str))
    (OUT / "license_report.json").write_text(json.dumps([r for r in results if "license" in r], indent=2, default=str))
    (OUT / "security_report.json").write_text(json.dumps({"status": "metadata_only", "notes": "Source scan not implemented"}, indent=2))
    (OUT / "secret_risk_report.json").write_text(json.dumps({"status": "metadata_only"}, indent=2))
    (OUT / "order_path_report.json").write_text(json.dumps({"status": "metadata_only"}, indent=2))
    (OUT / "adapter_plan.json").write_text(json.dumps({"plans": []}, indent=2))
    (OUT / "reference_mining_report.json").write_text(json.dumps({"reference_mines": [r for r in results if r.get("verdict") == "REFERENCE_MINE"]}, indent=2, default=str))
    (OUT / "rejected_repos.json").write_text(json.dumps([r for r in results if str(r.get("verdict", "")).startswith("REJECT")], indent=2, default=str))
    (OUT / "discovered_repos.json").write_text(json.dumps({"status": "metadata_only", "discovered": []}, indent=2))
    (OUT / "import_verdicts.json").write_text(json.dumps({"verdicts": []}, indent=2))
    return results

if __name__ == "__main__":
    asyncio.run(run_harvester())
