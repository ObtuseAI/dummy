from core.ontology import RepoVerdict

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
            "emits_native_types": True,
            "notes": f"Strategy hits: {len(scan['strategy_hits'])}, forecast hits: {len(scan['forecast_hits'])}, risk hits: {len(scan['risk_hits'])}",
        }] if verdict == RepoVerdict.ADAPTER_TARGET else []
    else:
        verdict = RepoVerdict.REFERENCE_MINE
        plans = []
    return {"repo": full, "verdict": verdict.value, "plans": plans, "scan_summary": scan}
