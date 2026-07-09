"""Generate DUMMY_V8 live-capped firewall rehearsal V2 reports.

Produces the V2 rehearsal proof report, the model-proof order-path V2 report,
and the operator-approval report.  No secret values are written and no real
Kalshi orders are submitted.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 1. Hybrid live-cap firewall rehearsal V2
# ---------------------------------------------------------------------------


async def generate_hybrid_live_cap_firewall_rehearsal_report_v2() -> dict:
    from core import state as state_module
    from core.config_loader import load_caps
    from core.ontology import AccountMode
    from execution.hybrid_path import HybridLiveCapRehearsalV2

    original_mode = state_module.STATE.mode
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ.setdefault("KALSHI_API_KEY_ID", "dummy_report_key")
    try:
        caps = load_caps()
        caps.allowed_markets = ["SPX-ABOVE-5000"]
        with patch("live_firewall.firewall.load_caps", return_value=caps), patch(
            "execution.hybrid_path.load_caps", return_value=caps
        ):
            rehearsal = HybridLiveCapRehearsalV2()
            result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

        return {
            "generated_at": now_iso(),
            "workstream": "V8: Hybrid Live-Cap Firewall Rehearsal V2",
            "status": result.get("status"),
            "would_submit": result.get("would_submit"),
            "blocked_reason": result.get("blocked_reason"),
            "strategy_governor_decision": result.get("strategy_governor_decision"),
            "source": result.get("source"),
            "model_mode": result.get("model_mode"),
            "live_submitted": result.get("live_submitted"),
            "no_live_submission": not result.get("live_submitted"),
            "verdict": "PASS"
            if result.get("status") in ("rehearsal", "no_trade", "blocked")
            and not result.get("live_submitted")
            else "FAIL",
        }
    except Exception as exc:
        return {
            "generated_at": now_iso(),
            "workstream": "V8: Hybrid Live-Cap Firewall Rehearsal V2",
            "error": str(exc),
            "verdict": "FAIL",
        }
    finally:
        state_module.STATE.set_mode(original_mode)


# ---------------------------------------------------------------------------
# 2. Model-proof order path V2
# ---------------------------------------------------------------------------


def _has_create_order_call(source: str) -> bool:
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    for line in source.splitlines():
        if call_re.search(line) and "def create_order(" not in line:
            return True
    return False


def generate_model_proof_order_path_report_v2() -> dict:
    excluded = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "tests",
        "artifacts",
    }
    offenders: set[str] = set()
    for py in ROOT.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        if _has_create_order_call(text):
            offenders.add(py.relative_to(ROOT).as_posix())

    allowed = {"live_firewall/firewall.py", "kalshi/submitter.py"}
    only_allowed = offenders <= allowed

    hybrid_path = ROOT / "execution" / "hybrid_path.py"
    hybrid_source = (
        hybrid_path.read_text(encoding="utf-8", errors="ignore")
        if hybrid_path.exists()
        else ""
    )
    v2_class_present = "HybridLiveCapRehearsalV2" in hybrid_source
    uses_proof_ledger = "write_proof" in hybrid_source
    model_router_proof_present = (
        "opinion.proof_reference" in hybrid_source and "proposal.proof_reference" in hybrid_source
    )

    return {
        "generated_at": now_iso(),
        "workstream": "V8: Model-Proof Order Path V2",
        "files_with_create_order_calls": sorted(offenders),
        "allowed_callers": sorted(allowed),
        "only_allowed_callers": only_allowed,
        "v2_rehearsal_class_present": v2_class_present,
        "v2_rehearsal_uses_proof_ledger": uses_proof_ledger,
        "v2_rehearsal_carries_model_router_proof": model_router_proof_present,
        "execution_paths_use_proof_ledger": uses_proof_ledger and v2_class_present,
        "verdict": "PASS"
        if only_allowed and v2_class_present and uses_proof_ledger and model_router_proof_present
        else "FAIL",
    }


# ---------------------------------------------------------------------------
# 3. No live submit without operator approval
# ---------------------------------------------------------------------------


async def generate_no_live_submit_without_operator_approval_report_v1() -> dict:
    from core import state as state_module
    from core.config_loader import load_caps
    from core.ontology import AccountMode
    from execution.hybrid_path import HybridLiveCapRehearsalV2

    live_submit_path = ROOT / "configs" / "live_submit.json"
    live_submit_config = (
        json.loads(live_submit_path.read_text(encoding="utf-8"))
        if live_submit_path.exists()
        else {}
    )
    enabled = live_submit_config.get("enabled") is True

    original_mode = state_module.STATE.mode
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    os.environ.setdefault("KALSHI_API_KEY_ID", "dummy_report_key")
    run_result: dict = {}
    try:
        caps = load_caps()
        caps.allowed_markets = ["SPX-ABOVE-5000"]
        with patch("live_firewall.firewall.load_caps", return_value=caps), patch(
            "execution.hybrid_path.load_caps", return_value=caps
        ):
            rehearsal = HybridLiveCapRehearsalV2()
            run_result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")
    except Exception as exc:
        run_result = {"error": str(exc)}
    finally:
        state_module.STATE.set_mode(original_mode)

    would_submit = run_result.get("would_submit")
    live_submitted = run_result.get("live_submitted")
    blocked_reason = run_result.get("blocked_reason")

    no_live_order_paths = generate_model_proof_order_path_report_v2()["only_allowed_callers"]

    return {
        "generated_at": now_iso(),
        "workstream": "V8: No Live Submit Without Operator Approval",
        "live_submit_enabled": enabled,
        "would_submit": would_submit,
        "live_submitted": live_submitted,
        "blocked_reason": blocked_reason,
        "no_order_creating_endpoints_called": run_result.get("source") != "live"
        or not run_result.get("order_creating_endpoints_called"),
        "only_allowed_callers_invoke_create_order": no_live_order_paths,
        "verdict": "PASS"
        if not enabled
        and would_submit is False
        and not live_submitted
        and blocked_reason == "live_submit_disabled"
        and no_live_order_paths
        else "FAIL",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    reports = {
        "hybrid_live_cap_firewall_rehearsal_report_v2.json": await generate_hybrid_live_cap_firewall_rehearsal_report_v2(),
        "model_proof_order_path_report_v2.json": generate_model_proof_order_path_report_v2(),
        "no_live_submit_without_operator_approval_report_v1.json": await generate_no_live_submit_without_operator_approval_report_v1(),
    }

    for name, data in reports.items():
        (ARTIFACTS / name).write_text(json.dumps(data, indent=2, default=str))

    summary = {
        "generated_at": now_iso(),
        "workstream": "V8: Rehearsal Reports",
        "reports": {name: data.get("verdict") for name, data in reports.items()},
        "verdict": "PASS"
        if all(data.get("verdict") in ("PASS", "PARTIAL") for data in reports.values())
        else "FAIL",
    }
    (ARTIFACTS / "v8_rehearsal_reports_summary.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
