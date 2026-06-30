from datetime import datetime, timezone, timedelta
from repo_harvester.github_client import fetch_repo_metadata, fetch_languages
from repo_harvester.classifier import classify_repo

async def audit_repo(owner: str, name: str) -> dict:
    meta = await fetch_repo_metadata(owner, name)
    langs = await fetch_languages(owner, name)
    verdict, reasons = classify_repo(meta)
    return {
        "owner": owner,
        "name": name,
        "url": meta.get("html_url", f"https://github.com/{owner}/{name}"),
        "license": (meta.get("license") or {}).get("spdx_id"),
        "last_pushed_at": datetime.fromisoformat(meta["pushed_at"].replace("Z", "+00:00")) if meta.get("pushed_at") else None,
        "languages": langs,
        "verdict": verdict.value,
        "verdict_reasons": reasons,
    }
