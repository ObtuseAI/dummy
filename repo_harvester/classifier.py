from datetime import datetime, timezone, timedelta
from core.ontology import RepoVerdict

SCRAPING_RISK_KEYWORDS = ["scraping", "bookmaker", "bookmakers", "odds scraping", "scrape"]

def _description_has_scraping_risk(meta: dict) -> bool:
    desc = (meta.get("description") or "").lower()
    return any(kw in desc for kw in SCRAPING_RISK_KEYWORDS)

def classify_repo(meta: dict, category: str | None = None):
    reasons = []
    # Sports repos that mention scraping/bookmakers are high compliance risk.
    if category == "sports_prediction_odds" and _description_has_scraping_risk(meta):
        reasons.append("Sports repo description mentions scraping/bookmaker")
        return RepoVerdict.REJECT_SCRAPING_RISK, reasons
    license_id = (meta.get("license") or {}).get("spdx_id")
    if not license_id or license_id in ["NOASSERTION", "NONE"]:
        reasons.append("No OSI license")
        return RepoVerdict.REJECT_LICENSE, reasons
    pushed_at = meta.get("pushed_at")
    if pushed_at:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - pushed > timedelta(days=730):
            reasons.append("Stale repo > 2 years")
            return RepoVerdict.REJECT_STALE, reasons
    # Heuristic: direct live-order bypass would require inspecting source; we cannot do that from metadata alone.
    # Stable libraries with permissive licenses become reference mines by default.
    if license_id in ["MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause"]:
        reasons.append("Permissive license; safe reference mine")
        return RepoVerdict.REFERENCE_MINE, reasons
    reasons.append("License OK but not obviously reusable")
    return RepoVerdict.REFERENCE_MINE, reasons
