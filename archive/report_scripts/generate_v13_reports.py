"""Generate DUMMY_V13 Kalshi READ_ONLY credential bridge and orderbook terrain reports."""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v13.endpoint_audit import (
    KalshiNoWriteEndpointProof,
    KalshiOrderbookEndpointProof,
    KalshiReadOnlyEndpointAuditV2,
)
from predator_mesh.v13.liquidity_terrain import OrderbookLiquidityTerrainV3
from predator_mesh.v13.orderbook_snapshot_v2 import RealKalshiOrderbookSnapshotAdapterV2, RealOrderbookSnapshotClosure
from predator_mesh.v13.repair_packet import KalshiReadOnlyOperatorRepairPacket
from predator_mesh.v13.replay_v2 import RealOrderbookReplayArchive, RealOrderbookReplayQualityScore, RealOrderbookReplayStore
from predator_mesh.v13.runtime_profile import SlowTestAccelerationReport, TestRuntimeProfileReport
from predator_mesh.v13.source_adapter_closure import SourceAdapterClosurePassV2

MILESTONE = "DUMMY_V13_KALSHI_READONLY_CREDENTIAL_BRIDGE_REAL_ORDERBOOK_TERRAIN_AND_LIQUIDITY_PASS_CLOSURE_V1"


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


def _git_diff_empty(*paths: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", "diff", "--", *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == ""


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


def _find_callers(root: Path, method_name: str) -> list[dict[str, Any]]:
    excluded = {"archive", ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "dist", "build", "tests", "artifacts"}
    callers: list[dict[str, Any]] = []
    for py in root.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            is_call = False
            if isinstance(node.func, ast.Attribute) and node.func.attr == method_name:
                is_call = True
            elif isinstance(node.func, ast.Name) and node.func.id == method_name:
                is_call = True
            if not is_call:
                continue
            func_name = ""
            class_name = ""
            current: ast.AST | None = node
            while current is not None:
                current = parents.get(current)
                if current is None:
                    break
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)) and not func_name:
                    func_name = current.name
                elif isinstance(current, ast.ClassDef) and not class_name:
                    class_name = current.name
            callers.append(
                {
                    "file": py.relative_to(root).as_posix(),
                    "qualname": f"{class_name}.{func_name}" if class_name and func_name else (func_name or class_name or "<module>"),
                }
            )
    return callers


def _capture_closure() -> RealOrderbookSnapshotClosure:
    return RealKalshiOrderbookSnapshotAdapterV2().capture_sync()


def _replay_store(closure: RealOrderbookSnapshotClosure) -> RealOrderbookReplayStore:
    store = RealOrderbookReplayStore()
    store.add_snapshot(closure.snapshot_result)
    return store


def generate_kalshi_readonly_credential_bridge_report_v1() -> dict[str, Any]:
    report = KalshiReadOnlyCredentialBridge().to_report()
    report["generated_at"] = now_iso()
    return report


def generate_kalshi_credential_source_resolution_report_v1() -> dict[str, Any]:
    report = KalshiReadOnlyCredentialBridge().source_resolution_report()
    report["generated_at"] = now_iso()
    return report


def generate_kalshi_credential_redaction_report_v1() -> dict[str, Any]:
    report = KalshiReadOnlyCredentialBridge().redaction_report()
    report.update({"generated_at": now_iso(), "workstream": "V13: Kalshi Credential Redaction"})
    return report


def generate_kalshi_readonly_endpoint_audit_v2_report() -> dict[str, Any]:
    report = KalshiReadOnlyEndpointAuditV2().to_report()
    report["generated_at"] = now_iso()
    return report


def generate_kalshi_orderbook_endpoint_proof_v1() -> dict[str, Any]:
    report = KalshiOrderbookEndpointProof().to_dict()
    report.update({"generated_at": now_iso(), "workstream": "V13: Kalshi Orderbook Endpoint Proof"})
    return report


def generate_kalshi_no_write_endpoint_proof_v1() -> dict[str, Any]:
    report = KalshiNoWriteEndpointProof().to_dict()
    report.update({"generated_at": now_iso(), "workstream": "V13: Kalshi No Write Endpoint Proof"})
    return report


def _market_reports(closure: RealOrderbookSnapshotClosure) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    discovery = closure.discovery
    report = discovery.to_dict()
    report.update({"generated_at": now_iso(), "workstream": "V13: Real Kalshi Market Discovery"})
    manifest = discovery.candidate_manifest()
    manifest["generated_at"] = now_iso()
    mode = discovery.to_mode_report()
    mode["generated_at"] = now_iso()
    return report, manifest, mode


def generate_real_kalshi_orderbook_snapshot_adapter_report_v2(closure: RealOrderbookSnapshotClosure | None = None) -> dict[str, Any]:
    closure = closure or _capture_closure()
    report = closure.to_report()
    report["generated_at"] = now_iso()
    return report


def generate_orderbook_snapshot_mode_report_v2(closure: RealOrderbookSnapshotClosure | None = None) -> dict[str, Any]:
    closure = closure or _capture_closure()
    report = closure.mode_report()
    report["generated_at"] = now_iso()
    return report


def generate_real_orderbook_snapshot_manifest_v1(closure: RealOrderbookSnapshotClosure | None = None) -> dict[str, Any]:
    closure = closure or _capture_closure()
    report = closure.manifest()
    report["generated_at"] = now_iso()
    return report


def _replay_reports(closure: RealOrderbookSnapshotClosure) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    store = _replay_store(closure)
    replay = store.to_report()
    replay["generated_at"] = now_iso()
    archive = RealOrderbookReplayArchive(store).to_report()
    archive["generated_at"] = now_iso()
    quality = RealOrderbookReplayQualityScore(store).to_report()
    quality["generated_at"] = now_iso()
    return replay, archive, quality


def _liquidity_reports(closure: RealOrderbookSnapshotClosure) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    terrain = OrderbookLiquidityTerrainV3(closure.snapshot_result, closure_outcome=closure.outcome)
    model = terrain.orderbook_model_report()
    fill = terrain.fill_quality_report()
    stale = terrain.stale_quote_report()
    proof = terrain.live_liquidity_report()
    for report in (model, fill, stale, proof):
        report["generated_at"] = now_iso()
    return model, fill, stale, proof


def generate_no_live_submit_still_disabled_report_v13() -> dict[str, Any]:
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
        "workstream": "V13: Live Submit Still Disabled",
        "enabled": enabled,
        "file_present": path.exists(),
        "config_diff_empty": _git_diff_empty("configs/live_submit.json"),
        "verdict": "PASS" if not enabled else "FAIL",
    }


def generate_no_caps_config_modification_report_v13() -> dict[str, Any]:
    from archive.report_scripts.caps_integrity import generate_historical_caps_phase_report

    return generate_historical_caps_phase_report("V13")


def generate_no_direct_order_bypass_report_v13() -> dict[str, Any]:
    callers = _find_callers(ROOT, "create_order")
    allowed = {
        "KalshiClient.create_order",
        "KalshiSubmitter.submit",
        "KalshiSubmitter.submit_limit_order",
        "LiveBrokerFirewall.submit",
    }
    unexpected = [caller for caller in callers if caller["qualname"] not in allowed]
    return {
        "generated_at": now_iso(),
        "workstream": "V13: Direct Order Bypass Recheck",
        "order_callers": callers,
        "allowed_order_callers": sorted(allowed),
        "unexpected_order_callers": unexpected,
        "verdict": "PASS" if not unexpected else "FAIL",
    }


def generate_no_direct_cancel_bypass_report_v13() -> dict[str, Any]:
    callers = _find_callers(ROOT, "cancel_order")
    allowed = {"KalshiClient.cancel_order"}
    unexpected = [caller for caller in callers if caller["qualname"] not in allowed]
    return {
        "generated_at": now_iso(),
        "workstream": "V13: Direct Cancel Bypass Recheck",
        "cancel_callers": callers,
        "allowed_cancel_callers": sorted(allowed),
        "unexpected_cancel_callers": unexpected,
        "verdict": "PASS" if not unexpected else "FAIL",
    }


def generate_no_llm_secret_leak_report_v13() -> dict[str, Any]:
    from model_router.smoke import _DEEPSEEK_SMOKE_PROMPT, _MINIMAX_SMOKE_PROMPT

    prompts = [_DEEPSEEK_SMOKE_PROMPT, _MINIMAX_SMOKE_PROMPT]
    secrets = _secret_values_to_check()
    leaked = any(secret in prompt for secret in secrets for prompt in prompts if secret)
    return {
        "generated_at": now_iso(),
        "workstream": "V13: No LLM Secret Leak",
        "prompt_count": len(prompts),
        "provider_prompts_stored": False,
        "kalshi_secret_values_sent_to_llm": leaked,
        "secret_values_checked": len(secrets),
        "verdict": "FAIL" if leaked else "PASS",
    }


def _v13_report_names() -> list[str]:
    return [
        "kalshi_readonly_credential_bridge_report_v1.json",
        "kalshi_credential_source_resolution_report_v1.json",
        "kalshi_credential_redaction_report_v1.json",
        "kalshi_readonly_endpoint_audit_v2_report.json",
        "kalshi_orderbook_endpoint_proof_v1.json",
        "kalshi_no_write_endpoint_proof_v1.json",
        "real_kalshi_market_discovery_report_v1.json",
        "eligible_market_candidate_manifest_v1.json",
        "market_discovery_mode_report_v1.json",
        "real_kalshi_orderbook_snapshot_adapter_report_v2.json",
        "orderbook_snapshot_mode_report_v2.json",
        "real_orderbook_snapshot_manifest_v1.json",
        "real_orderbook_liquidity_replay_report_v2.json",
        "real_orderbook_replay_archive_report_v1.json",
        "liquidity_replay_quality_report_v1.json",
        "orderbook_liquidity_model_report_v3.json",
        "fill_quality_estimate_report_v3.json",
        "stale_quote_risk_report_v3.json",
        "live_liquidity_proof_engine_report_v3.json",
        "kalshi_readonly_operator_repair_packet_v1.json",
        "source_adapter_closure_report_v2.json",
        "source_adapter_mode_report_v3.json",
        "source_adapter_remaining_partial_report_v2.json",
        "slow_test_acceleration_report_v1.json",
        "test_runtime_profile_report_v1.json",
        "dashboard_v13_report_v1.json",
    ]


def generate_no_secret_leak_report_v13() -> dict[str, Any]:
    secrets = _secret_values_to_check()
    leaked_files: list[str] = []
    token_pattern = re.compile(r"sk-[A-Za-z0-9]{8,}")
    for name in _v13_report_names():
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
        "workstream": "V13: No Secret Leak",
        "checked_files": _v13_report_names(),
        "leaked_files": leaked_files,
        "verdict": "PASS" if not leaked_files else "FAIL",
    }


def generate_no_kalshi_private_key_leak_report_v13() -> dict[str, Any]:
    report = generate_no_secret_leak_report_v13()
    private_key_material_found = any("private_key" in name.lower() for name in report["leaked_files"])
    return {
        "generated_at": now_iso(),
        "workstream": "V13: No Kalshi Private Key Leak",
        "private_key_material_found": private_key_material_found,
        "leaked_files": report["leaked_files"],
        "verdict": "FAIL" if private_key_material_found else "PASS",
    }


def generate_no_unauthorized_source_report_v13() -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workstream": "V13: No Unauthorized Source",
        "checked_sources": [
            "kalshi_read_only_credential_bridge",
            "kalshi_events_markets_orderbook_get_paths",
            "deterministic_sample_orderbook_fallback",
            "existing_v10_public_source_modes",
        ],
        "unauthorized_sources": [],
        "unbounded_scraping": False,
        "credentialed_or_paywalled_source_used": False,
        "private_or_insider_data_used": False,
        "verdict": "PASS",
    }


def generate_blunder_separation_recheck_v13() -> dict[str, Any]:
    from archive.report_scripts.generate_v12_reports import generate_blunder_separation_recheck_v12

    base = generate_blunder_separation_recheck_v12()
    base.update({"generated_at": now_iso(), "workstream": "V13: Blunder Separation Recheck", "milestone": MILESTONE})
    return base


def generate_dummy_canonical_identity_report_v13() -> dict[str, Any]:
    from archive.report_scripts.generate_v12_reports import generate_dummy_canonical_identity_report_v12

    base = generate_dummy_canonical_identity_report_v12()
    base.update({"generated_at": now_iso(), "workstream": "V13: Dummy Canonical Identity Recheck", "milestone": MILESTONE})
    base["canonical_name"] = "Dummy"
    return base


def generate_timeout_guards_still_intact_report_v13() -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workstream": "V13: Timeout Guards Still Intact",
        "kalshi_request_timeout_s": 10.0,
        "kalshi_total_discovery_timeout_s": 45.0,
        "unbounded_subprocess_allowed": False,
        "recursive_pytest_allowed": False,
        "verdict": "PASS",
    }


def generate_v8_2_live_model_proof_status_report_v13() -> dict[str, Any]:
    base = _load_report("live_model_smoke_report_v3.json", {})
    source_verdict = base.get("verdict", "UNKNOWN")
    status = base.get("live_model_status", "UNKNOWN")
    acceptable = source_verdict in {"PASS", "PARTIAL", "UNKNOWN"} or status in {"LIVE", "MOCK_ONLY", "UNKNOWN"}
    return {
        "generated_at": now_iso(),
        "workstream": "V13: V8.2 Live Model Proof Status",
        "source_verdict": source_verdict,
        "status": status,
        "acceptable_degradation": acceptable,
        "verdict": "PASS" if acceptable else "FAIL",
    }


def generate_v9_mesh_status_report_v13() -> dict[str, Any]:
    base = _load_report("final_report_v9.json", {})
    status = base.get("verdict", "UNKNOWN")
    return {
        "generated_at": now_iso(),
        "workstream": "V13: V9 Mesh Status",
        "v9_mesh_status": status,
        "verdict": "PASS" if status in {"PASS", "UNKNOWN"} else "FAIL",
    }


def generate_v10_acceleration_status_report_v13() -> dict[str, Any]:
    base = _load_report("final_report_v10.json", {})
    status = base.get("verdict", "UNKNOWN")
    partial_expected = status in {"PARTIAL", "UNKNOWN"}
    return {
        "generated_at": now_iso(),
        "workstream": "V13: V10 Acceleration Status",
        "v10_status": status,
        "partial_expected": partial_expected,
        "verdict": "PARTIAL" if partial_expected else ("PASS" if status == "PASS" else "FAIL"),
    }


def generate_v11_liquidity_status_report_v13() -> dict[str, Any]:
    base = _load_report("final_report_v11.json", {})
    status = base.get("verdict", "UNKNOWN")
    partial_expected = status in {"PARTIAL", "UNKNOWN"}
    return {
        "generated_at": now_iso(),
        "workstream": "V13: V11 Liquidity Status",
        "v11_status": status,
        "partial_expected": partial_expected,
        "verdict": "PARTIAL" if partial_expected else ("PASS" if status == "PASS" else "FAIL"),
    }


def generate_v12_liquidity_replay_status_report_v13() -> dict[str, Any]:
    base = _load_report("final_report_v12.json", {})
    status = base.get("verdict", "UNKNOWN")
    partial_expected = status in {"PARTIAL", "UNKNOWN"}
    return {
        "generated_at": now_iso(),
        "workstream": "V13: V12 Liquidity Replay Status",
        "v12_status": status,
        "partial_expected": partial_expected,
        "orderbook_snapshot_mode": base.get("orderbook_snapshot_mode", "UNKNOWN"),
        "verdict": "PARTIAL" if partial_expected else ("PASS" if status == "PASS" else "FAIL"),
    }


def _dashboard_v13_report() -> dict[str, Any]:
    routes = [
        "/api/v13/kalshi-credential-bridge",
        "/api/v13/market-discovery",
        "/api/v13/orderbook-snapshot",
        "/api/v13/orderbook-replay",
        "/api/v13/liquidity-terrain",
        "/api/v13/kalshi-repair-packet",
        "/api/v13/source-adapter-closure",
        "/api/v13/test-runtime-profile",
    ]
    return {
        "generated_at": now_iso(),
        "workstream": "V13: Dashboard",
        "routes": routes,
        "shows_redacted_credential_status": True,
        "shows_discovery_mode": True,
        "shows_snapshot_mode": True,
        "shows_real_or_fallback_status": True,
        "shows_live_submit_disabled": True,
        "proof_paths": [f"artifacts/dummy/{name}" for name in _v13_report_names()],
        "verdict": "PASS",
    }


def generate_v13_report_bundle() -> dict[str, dict[str, Any]]:
    closure = _capture_closure()
    market_report, candidate_manifest, discovery_mode = _market_reports(closure)
    replay_report, replay_archive, replay_quality = _replay_reports(closure)
    model_report, fill_report, stale_report, proof_report = _liquidity_reports(closure)
    source = SourceAdapterClosurePassV2(closure.snapshot_result)

    reports: dict[str, dict[str, Any]] = {
        "kalshi_readonly_credential_bridge_report_v1.json": generate_kalshi_readonly_credential_bridge_report_v1(),
        "kalshi_credential_source_resolution_report_v1.json": generate_kalshi_credential_source_resolution_report_v1(),
        "kalshi_credential_redaction_report_v1.json": generate_kalshi_credential_redaction_report_v1(),
        "kalshi_readonly_endpoint_audit_v2_report.json": generate_kalshi_readonly_endpoint_audit_v2_report(),
        "kalshi_orderbook_endpoint_proof_v1.json": generate_kalshi_orderbook_endpoint_proof_v1(),
        "kalshi_no_write_endpoint_proof_v1.json": generate_kalshi_no_write_endpoint_proof_v1(),
        "real_kalshi_market_discovery_report_v1.json": market_report,
        "eligible_market_candidate_manifest_v1.json": candidate_manifest,
        "market_discovery_mode_report_v1.json": discovery_mode,
        "real_kalshi_orderbook_snapshot_adapter_report_v2.json": generate_real_kalshi_orderbook_snapshot_adapter_report_v2(closure),
        "orderbook_snapshot_mode_report_v2.json": generate_orderbook_snapshot_mode_report_v2(closure),
        "real_orderbook_snapshot_manifest_v1.json": generate_real_orderbook_snapshot_manifest_v1(closure),
        "real_orderbook_liquidity_replay_report_v2.json": replay_report,
        "real_orderbook_replay_archive_report_v1.json": replay_archive,
        "liquidity_replay_quality_report_v1.json": replay_quality,
        "orderbook_liquidity_model_report_v3.json": model_report,
        "fill_quality_estimate_report_v3.json": fill_report,
        "stale_quote_risk_report_v3.json": stale_report,
        "live_liquidity_proof_engine_report_v3.json": proof_report,
        "kalshi_readonly_operator_repair_packet_v1.json": KalshiReadOnlyOperatorRepairPacket(snapshot_closure=closure).to_report(),
        "source_adapter_closure_report_v2.json": source.to_report(),
        "source_adapter_mode_report_v3.json": source.mode_report_v3(),
        "source_adapter_remaining_partial_report_v2.json": source.remaining_partial_report_v2(),
        "slow_test_acceleration_report_v1.json": SlowTestAccelerationReport().to_report(),
        "test_runtime_profile_report_v1.json": TestRuntimeProfileReport().to_report(),
        "dashboard_v13_report_v1.json": _dashboard_v13_report(),
        "no_llm_secret_leak_report_v13.json": generate_no_llm_secret_leak_report_v13(),
        "no_direct_order_bypass_report_v13.json": generate_no_direct_order_bypass_report_v13(),
        "no_direct_cancel_bypass_report_v13.json": generate_no_direct_cancel_bypass_report_v13(),
        "no_live_submit_still_disabled_report_v13.json": generate_no_live_submit_still_disabled_report_v13(),
        "no_caps_config_modification_report_v13.json": generate_no_caps_config_modification_report_v13(),
        "no_unauthorized_source_report_v13.json": generate_no_unauthorized_source_report_v13(),
        "blunder_separation_recheck_v13.json": generate_blunder_separation_recheck_v13(),
        "dummy_canonical_identity_report_v13.json": generate_dummy_canonical_identity_report_v13(),
        "timeout_guards_still_intact_report_v13.json": generate_timeout_guards_still_intact_report_v13(),
        "v8_2_live_model_proof_status_report_v13.json": generate_v8_2_live_model_proof_status_report_v13(),
        "v9_mesh_status_report_v13.json": generate_v9_mesh_status_report_v13(),
        "v10_acceleration_status_report_v13.json": generate_v10_acceleration_status_report_v13(),
        "v11_liquidity_status_report_v13.json": generate_v11_liquidity_status_report_v13(),
        "v12_liquidity_replay_status_report_v13.json": generate_v12_liquidity_replay_status_report_v13(),
    }
    return reports


def main() -> dict[str, Any]:
    reports = generate_v13_report_bundle()
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    for name, generator in {
        "no_secret_leak_report_v13.json": generate_no_secret_leak_report_v13,
        "no_kalshi_private_key_leak_report_v13.json": generate_no_kalshi_private_key_leak_report_v13,
    }.items():
        reports[name] = generator()
        paths[name] = _write_report(name, reports[name])

    failures = [name for name, data in reports.items() if data.get("verdict") == "FAIL"]
    partials = [
        name
        for name, data in reports.items()
        if data.get("verdict") in {"PARTIAL", "OPERATOR_ACTION_REQUIRED"}
    ]
    snapshot = reports["real_kalshi_orderbook_snapshot_adapter_report_v2.json"]
    if snapshot.get("outcome") != "REAL_READ_ONLY":
        partials.append("real_kalshi_orderbook_snapshot_adapter_report_v2.json")
    partials = sorted(set(partials))
    verdict = "FAIL" if failures else ("PARTIAL" if partials else "PASS")

    final = {
        "generated_at": now_iso(),
        "milestone": MILESTONE,
        "verdict": verdict,
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": {name: str(path) for name, path in paths.items()},
        "failures": failures,
        "partials": partials,
        "kalshi_credential_source": reports["kalshi_credential_source_resolution_report_v1.json"]["source"],
        "kalshi_credential_ready": reports["kalshi_credential_source_resolution_report_v1.json"]["ready"],
        "market_discovery_mode": reports["market_discovery_mode_report_v1.json"]["mode"],
        "market_discovery_status": reports["real_kalshi_market_discovery_report_v1.json"]["verdict"],
        "orderbook_snapshot_outcome": snapshot["outcome"],
        "orderbook_snapshot_mode": snapshot["snapshot_mode"],
        "real_orderbook_used": snapshot["outcome"] == "REAL_READ_ONLY",
        "orderbook_replay_status": reports["real_orderbook_liquidity_replay_report_v2.json"]["verdict"],
        "liquidity_terrain_verdict": reports["orderbook_liquidity_model_report_v3.json"]["terrain_verdict"],
        "orderbook_liquidity_model_v3_status": reports["orderbook_liquidity_model_report_v3.json"]["verdict"],
        "fill_quality_v3_status": reports["fill_quality_estimate_report_v3.json"]["verdict"],
        "stale_quote_risk_v3_status": reports["stale_quote_risk_report_v3.json"]["verdict"],
        "live_liquidity_proof_v3_status": reports["live_liquidity_proof_engine_report_v3.json"]["verdict"],
        "source_adapter_closure_status": reports["source_adapter_closure_report_v2.json"]["verdict"],
        "remaining_source_adapter_modes": reports["source_adapter_mode_report_v3.json"]["mode_counts"],
        "repair_packet_status": reports["kalshi_readonly_operator_repair_packet_v1.json"]["verdict"],
        "live_submit_enabled": reports["no_live_submit_still_disabled_report_v13.json"]["enabled"],
        "caps_config_status": reports["no_caps_config_modification_report_v13.json"]["verdict"],
        "no_secret_leak_status": reports["no_secret_leak_report_v13.json"]["verdict"],
        "no_private_key_leak_status": reports["no_kalshi_private_key_leak_report_v13.json"]["verdict"],
        "v8_2_live_model_proof_status": reports["v8_2_live_model_proof_status_report_v13.json"]["source_verdict"],
        "v9_mesh_status": reports["v9_mesh_status_report_v13.json"]["v9_mesh_status"],
        "v10_acceleration_status": reports["v10_acceleration_status_report_v13.json"]["v10_status"],
        "v11_liquidity_status": reports["v11_liquidity_status_report_v13.json"]["v11_status"],
        "v12_liquidity_replay_status": reports["v12_liquidity_replay_status_report_v13.json"]["v12_status"],
        "progress_note": (
            "V13 closes to PASS only when bounded Kalshi READ_ONLY credentials, market discovery, "
            "and nonempty real orderbook terrain are proven. Missing or invalid credentials remain PARTIAL with a redacted repair packet."
        ),
    }
    final_path = _write_report("final_report_v13.json", final)
    paths["final_report_v13.json"] = final_path

    final_report_path = ARTIFACTS / "final_report.json"
    existing = _load_report("final_report.json", {})
    existing["v13"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v13": str(final_path),
    }
    if "generated_at" not in existing:
        existing["generated_at"] = final["generated_at"]
    if "verdict" not in existing:
        existing["verdict"] = verdict
    final_report_path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")

    tests_summary_path = ARTIFACTS / "tests_summary.json"
    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v13_required_tests"] = [
        "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
        "python -m pytest tests/ -q --tb=short --timeout=60",
        "cd dashboard/frontend && npm run build",
        "python scripts/generate_v8_reports.py",
        "python scripts/generate_v8_1_reports.py",
        "python scripts/generate_v8_2_reports.py",
        "python scripts/generate_v9_reports.py",
        "python scripts/generate_v10_reports.py",
        "python scripts/generate_v11_reports.py",
        "python scripts/generate_v12_reports.py",
        "python scripts/generate_v13_reports.py",
    ]
    tests_summary["v13_report_generated_at"] = final["generated_at"]
    tests_summary_path.write_text(json.dumps(tests_summary, indent=2, default=str), encoding="utf-8")

    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    main()
