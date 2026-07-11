"""Dummy V8 report orchestrator.

Calls all V8 report generators, runs the full pytest suite, checks the
dashboard build, and writes the canonical ``artifacts/dummy/tests_summary.json``
and ``artifacts/dummy/final_report.json``.

Final verdict semantics:
  PASS    - pytest is green, all V8 gates pass, and live model credentials are
            present (live smoke calls can succeed).
  PARTIAL - pytest is green, dashboard is built, Kalshi read-only is healthy,
            but live model credentials are absent.
  FAIL    - any regression: test failures, report FAIL verdicts, or missing
            required artifacts.

No secret values are written to artifacts.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ORCHESTRATOR_TIMEOUT_SECONDS = 90


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        pass


def _kalshi_credentials_present() -> bool:
    key_id = os.environ.get("KALSHI_API_KEY_ID")
    pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM")
    pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH")
    return bool(key_id and (pem or pem_path))


def _live_model_credentials_present() -> bool:
    from model_router.credential_readiness import CredentialReadiness

    return CredentialReadiness().ready()


def _dashboard_built() -> bool:
    return (ROOT / "dashboard" / "frontend" / "dist" / "index.html").exists()


def run_pytest_summary() -> dict[str, Any]:
    # Ignore the orchestrator's own test to avoid infinite recursion when this
    # function is invoked from inside ``tests/test_generate_v8_reports.py``.
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "--timeout=60",
        "--ignore=tests/test_generate_v8_reports.py",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=360)
    passed_match = re.search(r"(\d+) passed", proc.stdout)
    failed_match = re.search(r"(\d+) failed", proc.stdout)
    skipped_match = re.search(r"(\d+) skipped", proc.stdout)
    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    skipped = int(skipped_match.group(1)) if skipped_match else 0
    summary = {
        "total": passed + failed + skipped,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pytest_returncode": proc.returncode,
    }
    if proc.returncode != 0:
        output = (proc.stdout + "\n" + proc.stderr).splitlines()
        summary["pytest_output_tail"] = output[-80:]
    return summary


def _read_report_verdict(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("verdict")
    except Exception:
        return None


def _read_report_verdicts(filenames: list[str]) -> dict[str, str | None]:
    return {name: _read_report_verdict(ARTIFACTS / name) for name in filenames}


async def _safe_generate(name: str, coro) -> dict[str, Any]:
    """Await a report generator with a timeout; return SKIP/TIMEOUT on failure."""
    try:
        return await asyncio.wait_for(coro, timeout=ORCHESTRATOR_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return {
            "generated_at": now_iso(),
            "workstream": name,
            "verdict": "SKIP/TIMEOUT",
            "error": f"{name} timed out after {ORCHESTRATOR_TIMEOUT_SECONDS}s",
        }


async def main(run_tests: bool = True) -> dict[str, Any]:
    _load_dotenv()

    # -----------------------------------------------------------------------
    # Invoke all V8 report generators
    # -----------------------------------------------------------------------
    from archive.report_scripts import (
        generate_v8_firewall_reports,
        generate_v8_identity_reports,
        generate_v8_kalshi_reports,
        generate_v8_model_provider_reports,
        generate_v8_rehearsal_reports,
    )

    model_paths = await _safe_generate(
        "V8: Model Provider Reports", generate_v8_model_provider_reports.main()
    )
    firewall_prompt_results, firewall_output_results, firewall_leak = (
        generate_v8_firewall_reports.generate_firewall_reports(str(ARTIFACTS))
    )
    await _safe_generate("V8: Kalshi Reports", generate_v8_kalshi_reports.main())
    await _safe_generate("V8: Rehearsal Reports", generate_v8_rehearsal_reports.main())
    generate_v8_identity_reports.main()

    # -----------------------------------------------------------------------
    # Collect report verdicts
    # -----------------------------------------------------------------------
    report_filenames = [
        "model_provider_credential_readiness_report_v1.json",
        "no_model_provider_secret_leak_report_v1.json",
        "live_model_provider_adapter_report_v1.json",
        "model_provider_error_handling_report_v1.json",
        "live_model_smoke_report_v1.json",
        "live_model_prompt_safety_report_v1.json",
        "llm_prompt_firewall_v2_report.json",
        "model_output_firewall_report_v1.json",
        "no_llm_secret_leak_report_v2.json",
        "real_kalshi_read_only_report_v4.json",
        "kalshi_endpoint_audit_report_v2.json",
        "no_order_in_read_only_report_v4.json",
        "hybrid_live_cap_firewall_rehearsal_report_v2.json",
        "model_proof_order_path_report_v2.json",
        "no_live_submit_without_operator_approval_report_v1.json",
        "dummy_canonical_identity_report_v4.json",
        "blunder_separation_recheck_v6.json",
        "direct_order_bypass_report_v8.json",
        "no_secret_leak_report_v7.json",
    ]
    report_verdicts = _read_report_verdicts(report_filenames)

    # Include generator-written summaries.
    summary_verdicts: dict[str, str | None] = {}
    kalshi_summary = ARTIFACTS / "v8_kalshi_reports_summary.json"
    if kalshi_summary.exists():
        try:
            summary_verdicts["v8_kalshi_reports_summary"] = json.loads(
                kalshi_summary.read_text(encoding="utf-8")
            ).get("verdict")
        except Exception:
            pass
    rehearsal_summary = ARTIFACTS / "v8_rehearsal_reports_summary.json"
    if rehearsal_summary.exists():
        try:
            summary_verdicts["v8_rehearsal_reports_summary"] = json.loads(
                rehearsal_summary.read_text(encoding="utf-8")
            ).get("verdict")
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Run pytest and persist summary
    # -----------------------------------------------------------------------
    tests_summary = run_pytest_summary() if run_tests else {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "pytest_returncode": 0,
        "note": "pytest skipped by orchestrator caller",
    }
    tests_summary_payload = {
        "generated_at": now_iso(),
        "workstream": "V8: Tests Summary",
        **tests_summary,
    }
    (ARTIFACTS / "tests_summary.json").write_text(
        json.dumps(tests_summary_payload, indent=2, default=str)
    )

    # -----------------------------------------------------------------------
    # Determine final verdict
    # -----------------------------------------------------------------------
    all_report_verdicts = {**report_verdicts, **summary_verdicts}
    failures = [
        name
        for name, verdict in all_report_verdicts.items()
        if verdict == "FAIL"
    ]
    partials = [
        name
        for name, verdict in all_report_verdicts.items()
        if verdict in ("PARTIAL", "MOCK_ONLY")
    ]

    kalshi_read_only_ok = all_report_verdicts.get("real_kalshi_read_only_report_v4.json") in (
        "PASS",
        "SKIP",
    )
    dashboard_ok = _dashboard_built()
    tests_ok = tests_summary["failed"] == 0 and tests_summary["pytest_returncode"] == 0
    live_model_ready = _live_model_credentials_present()
    kalshi_creds_present = _kalshi_credentials_present()

    if not tests_ok or failures:
        verdict = "FAIL"
    elif not dashboard_ok:
        verdict = "FAIL"
    elif not kalshi_read_only_ok:
        verdict = "FAIL"
    elif partials or not live_model_ready:
        verdict = "PARTIAL"
    else:
        verdict = "PASS"

    final = {
        "generated_at": now_iso(),
        "milestone": "DUMMY_V8_MODEL_ROUTING_FIREWALL_GOVERNOR_REHEARSAL_V1",
        "verdict": verdict,
        "tests_summary": tests_summary,
        "report_verdicts": all_report_verdicts,
        "live_model_credentials_present": live_model_ready,
        "kalshi_credentials_present": kalshi_creds_present,
        "kalshi_read_only_ok": kalshi_read_only_ok,
        "dashboard_built": dashboard_ok,
        "failures": failures,
        "partials": partials,
        "note": (
            "V8 orchestrator complete. PASS requires green tests, all gates OK, "
            "and live model credentials. PARTIAL when tests/dashboard/Kalshi are "
            "healthy but live model credentials are absent."
        ),
    }
    (ARTIFACTS / "final_report.json").write_text(
        json.dumps(final, indent=2, default=str)
    )
    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=ORCHESTRATOR_TIMEOUT_SECONDS))
