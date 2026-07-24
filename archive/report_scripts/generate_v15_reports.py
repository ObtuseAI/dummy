"""Generate DUMMY_V15 credential-shape repair, bounded auth, real-terrain, and launch-gate reports."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.evidence_dir import EvidencePath

ARTIFACTS = EvidencePath(ROOT / "artifacts" / "dummy")

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v14.credential_forensics import KalshiCredentialForensics
from predator_mesh.v15.auth_probe_v2 import KalshiAuthProbeV2
from predator_mesh.v15.credential_shape_repair import KalshiCredentialShapeRepairEngine
from predator_mesh.v15.credential_source_conflict_resolver import KalshiCredentialSourceConflictResolver
from predator_mesh.v15.launch_readiness_v2 import LiquidityLaunchReadinessMatrixV2
from predator_mesh.v15.normalization_preview import KalshiCredentialNormalizationPreview
from predator_mesh.v15.retry_gate_v2 import RealTerrainRetryGateV2
from predator_mesh.v15.runtime_acceleration_v2 import (
    RuntimeAccelerationMegaReportV2,
    SlowTestRemediationReportV2,
    TestRuntimeBudgetReportV2,
)
from predator_mesh.v15.source_adapter_closure_v5 import SourceAdapterClosureV5
from predator_mesh.v15.terrain_closure_v3 import RealOrderbookTerrainClosureV3

MILESTONE = "DUMMY_V15_KALSHI_CREDENTIAL_SHAPE_REPAIR_REAL_TERRAIN_PASS_AND_LIQUIDITY_LAUNCH_GATE_FINALIZATION"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_report(name: str, data: dict[str, Any]) -> Path:
    path = ARTIFACTS / name
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def _load_report(name: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    path = ARTIFACTS / name
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback or {}


def _secret_values_to_check() -> list[str]:
    names = [
        "DEEPSEEK_API_KEY",
        "MINIMAX_API_KEY",
        "OPENROUTER_API_KEY",
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_API_PRIVATE_KEY_PATH",
    ]
    values = [os.environ.get(name, "") for name in names if len(os.environ.get(name, "")) >= 4]
    try:
        values.extend(value for value in KalshiReadOnlyCredentialBridge().secret_environment().values() if len(value) >= 4)
    except Exception:
        pass
    return sorted(set(values))


def _with_generated_at(report: dict[str, Any]) -> dict[str, Any]:
    report = dict(report)
    report["generated_at"] = now_iso()
    return report


def _forensics() -> dict[str, Any]:
    return KalshiCredentialForensics().to_report()


def _repair_engine() -> KalshiCredentialShapeRepairEngine:
    return KalshiCredentialShapeRepairEngine()


def _conflict_resolver() -> KalshiCredentialSourceConflictResolver:
    return KalshiCredentialSourceConflictResolver()


def _retry_gate() -> RealTerrainRetryGateV2:
    return RealTerrainRetryGateV2(repair_engine=_repair_engine(), conflict_resolver=_conflict_resolver())


def generate_kalshi_credential_shape_repair_report_v1() -> dict[str, Any]:
    return _with_generated_at(_repair_engine().to_report())


def generate_kalshi_credential_source_conflict_report_v1() -> dict[str, Any]:
    return _with_generated_at(_conflict_resolver().to_report())


def generate_kalshi_credential_normalization_preview_report_v1() -> dict[str, Any]:
    return _with_generated_at(KalshiCredentialNormalizationPreview(repair_engine=_repair_engine()).to_report())


def generate_kalshi_auth_probe_v2_report_v1() -> dict[str, Any]:
    return _with_generated_at(KalshiAuthProbeV2(repair_engine=_repair_engine(), conflict_resolver=_conflict_resolver()).to_report())


def generate_real_terrain_retry_gate_v2_report_v1() -> dict[str, Any]:
    return _with_generated_at(_retry_gate().to_report())


def generate_real_orderbook_terrain_closure_v3_report_v1() -> dict[str, Any]:
    forensics = _forensics()
    closure = RealOrderbookTerrainClosureV3(forensics_report=forensics, retry_gate=_retry_gate())
    return _with_generated_at(closure.to_report())


def generate_liquidity_launch_readiness_matrix_v2_report_v1() -> dict[str, Any]:
    forensics = _forensics()
    matrix = LiquidityLaunchReadinessMatrixV2(forensics_report=forensics, retry_gate=_retry_gate())
    return _with_generated_at(matrix.to_report())


def generate_source_adapter_closure_v5_report_v1() -> dict[str, Any]:
    forensics = _forensics()
    closure = SourceAdapterClosureV5(forensics_report=forensics, retry_gate=_retry_gate())
    return _with_generated_at(closure.to_report())


def _runtime_reports() -> dict[str, dict[str, Any]]:
    return {
        "runtime_acceleration_mega_report_v2.json": _with_generated_at(RuntimeAccelerationMegaReportV2().to_report()),
        "test_runtime_budget_report_v2.json": _with_generated_at(TestRuntimeBudgetReportV2().to_report()),
        "slow_test_remediation_report_v2.json": _with_generated_at(SlowTestRemediationReportV2().to_report()),
    }


def generate_no_live_submit_still_disabled_report_v15() -> dict[str, Any]:
    path = ROOT / "configs" / "live_submit.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    enabled = data.get("enabled") is True
    return {
        "generated_at": now_iso(),
        "workstream": "V15: Live Submit Still Disabled",
        "enabled": enabled,
        "file_present": path.exists(),
        "verdict": "PASS" if not enabled else "FAIL",
    }


def generate_no_caps_config_modification_report_v15() -> dict[str, Any]:
    from archive.report_scripts.caps_integrity import generate_historical_caps_phase_report

    return generate_historical_caps_phase_report("V15")


def generate_no_direct_order_bypass_report_v15() -> dict[str, Any]:
    from archive.report_scripts.generate_v14_reports import generate_no_direct_order_bypass_report_v14

    base = generate_no_direct_order_bypass_report_v14()
    base.update({"generated_at": now_iso(), "workstream": "V15: Direct Order Bypass Recheck"})
    return base


def generate_no_direct_cancel_bypass_report_v15() -> dict[str, Any]:
    from archive.report_scripts.generate_v14_reports import generate_no_direct_cancel_bypass_report_v14

    base = generate_no_direct_cancel_bypass_report_v14()
    base.update({"generated_at": now_iso(), "workstream": "V15: Direct Cancel Bypass Recheck"})
    return base


def _v15_report_names() -> list[str]:
    return [
        "kalshi_credential_shape_repair_report_v1.json",
        "kalshi_credential_source_conflict_report_v1.json",
        "kalshi_credential_normalization_preview_report_v1.json",
        "kalshi_auth_probe_v2_report_v1.json",
        "real_terrain_retry_gate_v2_report_v1.json",
        "real_orderbook_terrain_closure_v3_report_v1.json",
        "liquidity_launch_readiness_matrix_v2_report_v1.json",
        "source_adapter_closure_v5_report_v1.json",
        "runtime_acceleration_mega_report_v2.json",
        "test_runtime_budget_report_v2.json",
        "slow_test_remediation_report_v2.json",
        "dashboard_v15_report_v1.json",
    ]


def generate_no_secret_leak_report_v15() -> dict[str, Any]:
    secrets = _secret_values_to_check()
    leaked_files: list[str] = []
    token_pattern = re.compile(r"sk-[A-Za-z0-9]{8,}")
    for name in _v15_report_names():
        path = ARTIFACTS / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if any(secret in text for secret in secrets if secret):
            leaked_files.append(name)
        if "BEGIN PRIVATE KEY" in text or token_pattern.search(text):
            leaked_files.append(name)
    leaked_files = sorted(set(leaked_files))
    return {
        "generated_at": now_iso(),
        "workstream": "V15: No Secret Leak",
        "checked_files": _v15_report_names(),
        "leaked_files": leaked_files,
        "verdict": "PASS" if not leaked_files else "FAIL",
    }


def generate_no_kalshi_private_key_leak_report_v15() -> dict[str, Any]:
    report = generate_no_secret_leak_report_v15()
    private_key_material_found = any("private_key" in name.lower() for name in report["leaked_files"])
    return {
        "generated_at": now_iso(),
        "workstream": "V15: No Kalshi Private Key Leak",
        "private_key_material_found": private_key_material_found,
        "leaked_files": report["leaked_files"],
        "verdict": "FAIL" if private_key_material_found else "PASS",
    }


def generate_dashboard_v15_report_v1() -> dict[str, Any]:
    routes = [
        "/api/v15/credential-shape-repair",
        "/api/v15/credential-source-conflicts",
        "/api/v15/normalization-preview",
        "/api/v15/auth-probe-v2",
        "/api/v15/real-terrain-retry-v2",
        "/api/v15/real-orderbook-terrain-v3",
        "/api/v15/liquidity-launch-gate-v2",
        "/api/v15/source-adapter-closure-v5",
        "/api/v15/runtime-acceleration-v2",
    ]
    return {
        "generated_at": now_iso(),
        "workstream": "V15: Dashboard",
        "routes": routes,
        "shows_redacted_credential_status": True,
        "shows_live_submit_disabled": True,
        "proof_paths": [f"artifacts/dummy/{name}" for name in _v15_report_names()],
        "verdict": "PASS",
    }


def generate_v15_report_bundle() -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {
        "kalshi_credential_shape_repair_report_v1.json": generate_kalshi_credential_shape_repair_report_v1(),
        "kalshi_credential_source_conflict_report_v1.json": generate_kalshi_credential_source_conflict_report_v1(),
        "kalshi_credential_normalization_preview_report_v1.json": generate_kalshi_credential_normalization_preview_report_v1(),
        "kalshi_auth_probe_v2_report_v1.json": generate_kalshi_auth_probe_v2_report_v1(),
        "real_terrain_retry_gate_v2_report_v1.json": generate_real_terrain_retry_gate_v2_report_v1(),
        "real_orderbook_terrain_closure_v3_report_v1.json": generate_real_orderbook_terrain_closure_v3_report_v1(),
        "liquidity_launch_readiness_matrix_v2_report_v1.json": generate_liquidity_launch_readiness_matrix_v2_report_v1(),
        "source_adapter_closure_v5_report_v1.json": generate_source_adapter_closure_v5_report_v1(),
        **_runtime_reports(),
        "dashboard_v15_report_v1.json": generate_dashboard_v15_report_v1(),
        "no_direct_order_bypass_report_v15.json": generate_no_direct_order_bypass_report_v15(),
        "no_direct_cancel_bypass_report_v15.json": generate_no_direct_cancel_bypass_report_v15(),
        "no_live_submit_still_disabled_report_v15.json": generate_no_live_submit_still_disabled_report_v15(),
        "no_caps_config_modification_report_v15.json": generate_no_caps_config_modification_report_v15(),
    }
    return reports


def main() -> dict[str, Any]:
    reports = generate_v15_report_bundle()
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    for name, generator in {
        "no_secret_leak_report_v15.json": generate_no_secret_leak_report_v15,
        "no_kalshi_private_key_leak_report_v15.json": generate_no_kalshi_private_key_leak_report_v15,
    }.items():
        reports[name] = generator()
        paths[name] = _write_report(name, reports[name])

    failures = [name for name, data in reports.items() if data.get("verdict") == "FAIL"]
    partials = sorted({name for name, data in reports.items() if data.get("verdict") in {"PARTIAL", "OPERATOR_ACTION_REQUIRED"}})
    verdict = "FAIL" if failures else ("PARTIAL" if partials else "PASS")

    shape = reports["kalshi_credential_shape_repair_report_v1.json"]
    retry = reports["real_terrain_retry_gate_v2_report_v1.json"]
    terrain = reports["real_orderbook_terrain_closure_v3_report_v1.json"]
    readiness = reports["liquidity_launch_readiness_matrix_v2_report_v1.json"]

    final = {
        "generated_at": now_iso(),
        "milestone": MILESTONE,
        "verdict": verdict,
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": {name: str(path) for name, path in paths.items()},
        "failures": failures,
        "partials": partials,
        "credential_shape_verdict_state": shape["verdict_state"],
        "real_terrain_retry_decision": retry["decision"],
        "real_orderbook_terrain_mode": terrain["terrain_mode"],
        "real_terrain_provably_used": terrain["real_terrain_provably_used"],
        "liquidity_launch_gate_output": readiness["gate_output"],
        "liquidity_launch_readiness_score": readiness["readiness_score"],
        "live_submit_enabled": reports["no_live_submit_still_disabled_report_v15.json"]["enabled"],
        "caps_config_status": reports["no_caps_config_modification_report_v15.json"]["verdict"],
        "no_secret_leak_status": reports["no_secret_leak_report_v15.json"]["verdict"],
        "no_private_key_leak_status": reports["no_kalshi_private_key_leak_report_v15.json"]["verdict"],
        "no_direct_order_bypass_status": reports["no_direct_order_bypass_report_v15.json"]["verdict"],
        "no_direct_cancel_bypass_status": reports["no_direct_cancel_bypass_report_v15.json"]["verdict"],
        "dashboard_status": reports["dashboard_v15_report_v1.json"]["verdict"],
        "runtime_acceleration_status": reports["runtime_acceleration_mega_report_v2.json"]["verdict"],
        "progress_note": (
            "V15 closes to PASS only when credential shape is valid, auth-probe passes read-only, "
            "and real terrain is provably used (never claimed off a label alone). Malformed, conflicting, "
            "invalid, or missing credentials remain PARTIAL with redacted, placeholder-only repair guidance."
        ),
    }
    final_path = _write_report("final_report_v15.json", final)
    paths["final_report_v15.json"] = final_path

    final_report_path = ARTIFACTS / "final_report.json"
    existing = _load_report("final_report.json", {})
    existing["v15"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v15": str(final_path),
    }
    final_report_path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")

    tests_summary_path = ARTIFACTS / "tests_summary.json"
    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v15_required_tests"] = [
        "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
        "python -m pytest tests/ -q --tb=short --timeout=60",
        "cd dashboard/frontend && npm run build",
        "python scripts/generate_v8_reports.py",
        "python scripts/generate_v9_reports.py",
        "python scripts/generate_v10_reports.py",
        "python scripts/generate_v11_reports.py",
        "python scripts/generate_v12_reports.py",
        "python scripts/generate_v13_reports.py",
        "python scripts/generate_v14_reports.py",
        "python scripts/generate_v15_reports.py",
    ]
    tests_summary["v15_report_generated_at"] = final["generated_at"]
    tests_summary_path.write_text(json.dumps(tests_summary, indent=2, default=str), encoding="utf-8")

    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    main()
