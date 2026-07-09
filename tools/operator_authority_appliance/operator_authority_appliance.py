"""External operator-side authority appliance for the DUMMY live-proof path.

This tool lives OUTSIDE Dummy's self-authorization path (predator_mesh/*). Dummy itself never creates
approval files, runtime/approvals, live-submit config, caps, or broker adapters. This appliance only
helps a human operator generate/verify/install operator-OWNED authority artifacts, and only after
explicit typed local confirmation. Every live-order path stays fail-closed: nothing here submits an
order, contacts a broker, enables live-submit, or modifies caps unless the operator supplies full
external authority AND the exact env gate, at which point it invokes the EXISTING Dummy execute-once
script unchanged. It does not add Dummy stages, gates, or V305+ architecture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

APPLIANCE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APPLIANCE_DIR / "templates"
# Dummy repo root (…/dummy). This appliance sits at dummy/tools/operator_authority_appliance/.
DUMMY_ROOT = APPLIANCE_DIR.parents[1]
ARTIFACTS_DIR = DUMMY_ROOT / "artifacts" / "dummy"
DEFAULT_RUNTIME_APPROVALS = DUMMY_ROOT / "runtime" / "approvals"

# The ONLY phrase that can authorize a bounded firewall-only pilot submit (mirrors staged_gate_common).
REQUIRED_PHRASE = "I approve Dummy to run one controlled production pilot through LiveBrokerFirewall only, with no market orders, strict caps, live-submit already operator-enabled, per-order fail-closed checks, and immediate pilot auto-lock"
REQUIRED_SCOPE = "one_controlled_production_pilot_via_firewall_only"
REQUIRED_PROOF_TARGET = "FIRST_REAL_PILOT_PROOF"
REQUIRED_ACKNOWLEDGE_RISK = "I understand this can place one real limit order only through LiveBrokerFirewall after all Dummy gates pass"
INSTALL_CONFIRM_PHRASE = "I authorize installing these operator-created authority files into Dummy runtime"

ENV_MODE = ("DUMMY_LIVE_PROOF_MODE", "1")
ENV_ACK = ("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")

ACKS = {
    "no_market_order_acknowledgment": "no market order",
    "strict_caps_acknowledgment": "strict caps",
    "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
    "per_order_fail_closed_acknowledgment": "per-order fail-closed",
    "pilot_auto_lock_acknowledgment": "immediate pilot auto-lock",
}

BROAD_TERMS = ["full live trading", "trade live markets", "enable live submit", "unlimited", "all markets", "grant full", "any order", "whenever"]
MARKET_ALLOW_TERMS = ["allow market", "market order allowed", "enable market order", "use market order"]
SCALE_AUTONOMY_TERMS = ["enable scale", "apply scale", "enable autonomy", "autonomous trading", "auto-scale"]

APPROVAL_FILENAME = "dummy_controlled_production_pilot_approval.json"
PACK_FILES = ["authority_manifest.json", APPROVAL_FILENAME, "live_submit_descriptor.json", "caps_descriptor.json", "firewall_adapter_descriptor.json"]

# Command sequences (existing Dummy scripts only; never modified here).
READONLY_CMDS = [
    [sys.executable, "scripts/run_dummy_proof_starvation_stop_rule.py"],
    [sys.executable, "scripts/run_dummy_operator_execution_fork.py"],
    [sys.executable, "scripts/run_dummy_execute_once_command_seal.py"],
    [sys.executable, "scripts/run_dummy_completion_lift_v10.py"],
]
AUTHORITY_CHECK_CMDS = [
    [sys.executable, "scripts/run_dummy_external_authority_import_wizard.py"],
    [sys.executable, "scripts/run_dummy_final_armability_runbook.py"],
    [sys.executable, "scripts/run_dummy_execute_once_command_seal.py"],
]
EXECUTE_ONCE_CMD = [sys.executable, "scripts/run_dummy_execute_once_final_proof_v7.py"]
POST_PROOF_CMDS = [
    [sys.executable, "scripts/run_dummy_post_proof_auto_intake_v4.py"],
    [sys.executable, "scripts/run_dummy_reconcile_forensic_auto_orchestrator_v6.py"],
    [sys.executable, "scripts/run_dummy_post_proof_route_autopilot.py"],
    [sys.executable, "scripts/run_dummy_completion_lift_v10.py"],
]

RUNBOOK = [
    "python scripts/run_dummy_external_authority_import_wizard.py",
    "python scripts/run_dummy_final_armability_runbook.py",
    "python scripts/run_dummy_execute_once_command_seal.py",
    f"{ENV_MODE[0]}={ENV_MODE[1]} {ENV_ACK[0]}={ENV_ACK[1]} python scripts/run_dummy_execute_once_final_proof_v7.py",
    "python scripts/run_dummy_post_proof_auto_intake_v4.py",
    "python scripts/run_dummy_reconcile_forensic_auto_orchestrator_v6.py",
    "python scripts/run_dummy_post_proof_route_autopilot.py",
    "python scripts/run_dummy_completion_lift_v10.py",
]


# ----------------------------- helpers -----------------------------

def _hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def env_gate_present(env: dict[str, str] | None = None) -> bool:
    env = env if env is not None else dict(os.environ)
    return env.get(ENV_MODE[0]) == ENV_MODE[1] and env.get(ENV_ACK[0]) == ENV_ACK[1]


def command_seal_status() -> str:
    v297 = _load_json(ARTIFACTS_DIR / "final_report_v297.json")
    status = str(v297.get("execute_once_command_seal_controller_status", "ABSENT"))
    # The seal artifact can be stale; require the runtime approval to still be installed.
    approval_path = DEFAULT_RUNTIME_APPROVALS / APPROVAL_FILENAME
    if not approval_path.exists():
        return "PARTIAL_COMMAND_SEAL_BLOCKED_APPROVAL_NOT_INSTALLED"
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except Exception:
        return "PARTIAL_COMMAND_SEAL_BLOCKED_APPROVAL_NOT_READABLE"
    if approval.get("scope") != REQUIRED_SCOPE:
        return "PARTIAL_COMMAND_SEAL_BLOCKED_APPROVAL_SCOPE_MISMATCH"
    return status


def proof_lock_exists() -> bool:
    """A real prior attempt artifact / proof lock makes a second attempt illegal."""
    v298 = _load_json(ARTIFACTS_DIR / "final_report_v298.json")
    return str(v298.get("execute_once_final_proof_runner_v7_controller_status", "")) == "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED" and int(v298.get("real_live_orders_submitted_count", 0) or 0) > 0


def _contains(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(t in low for t in terms)


# ----------------------------- templates -----------------------------

def _templates() -> dict[str, dict[str, Any]]:
    approval = {"_marker": "NOT_APPROVAL_TEMPLATE_ONLY", "exact_phrase": "<REQUIRED_EXACT_PHRASE>",
                "operator": "<operator>", "timestamp": "<iso>", "reason": "<reason>", "scope": REQUIRED_SCOPE,
                "expiration": "<iso>"}
    approval.update({k: v for k, v in ACKS.items()})
    return {
        "authority_manifest.template.json": {"_marker": "NOT_APPROVAL_TEMPLATE_ONLY", "version": "v3",
            "proof_target": REQUIRED_PROOF_TARGET, "scope": REQUIRED_SCOPE, "reason": "<reason>",
            "operator_metadata": {"operator": "<operator>", "timestamp": "<iso>"}, "expiry": "<iso>",
            "config_descriptors": {"live_submit": "<bool>", "caps": "<bool>"}, "adapter_descriptors": {"firewall": "<bool>"},
            "approvals": {"exact_phrase": "<REQUIRED_EXACT_PHRASE>"}, "not_self_authorized_by_dummy": True},
        "approval_packet.template.json": approval,
        "live_submit_descriptor.template.json": {"_marker": "NOT_APPROVAL_TEMPLATE_ONLY", "live_submit_enabled": "<bool_operator_enabled>", "operator_confirmed": "<bool>"},
        "caps_descriptor.template.json": {"_marker": "NOT_APPROVAL_TEMPLATE_ONLY", "caps_confirmed": "<bool>", "strict_caps": True, "operator_confirmed": "<bool>"},
        "firewall_adapter_descriptor.template.json": {"_marker": "NOT_APPROVAL_TEMPLATE_ONLY", "firewall_adapter_injected": "<bool_operator_injected>", "non_broker_double": "<bool>", "operator_confirmed": "<bool>"},
    }


def init_templates() -> list[str]:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for name, data in _templates().items():
        path = TEMPLATES_DIR / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        written.append(str(path))
    return written


# ----------------------------- build / verify / install -----------------------------

def build_authority_pack(*, output_dir: Path, operator: str, reason: str, expires_at: str, proof_target: str,
                         typed_approval: str, acknowledge_risk: str) -> dict[str, Any]:
    errors: list[str] = []
    if not operator:
        errors.append("MISSING_OPERATOR")
    if not reason:
        errors.append("MISSING_REASON")
    if not expires_at:
        errors.append("MISSING_EXPIRY")
    if proof_target != REQUIRED_PROOF_TARGET:
        errors.append("INVALID_PROOF_TARGET")
    if typed_approval != REQUIRED_PHRASE:
        errors.append("APPROVAL_PHRASE_NOT_EXACT")
    if acknowledge_risk != REQUIRED_ACKNOWLEDGE_RISK:
        errors.append("RISK_ACK_NOT_EXACT")
    combined = f"{reason} {acknowledge_risk}"
    if _contains(combined, BROAD_TERMS) or _contains(typed_approval, BROAD_TERMS):
        errors.append("BROAD_APPROVAL_REJECTED")
    if _contains(combined, MARKET_ALLOW_TERMS):
        errors.append("MARKET_ORDER_APPROVAL_REJECTED")
    if _contains(combined, SCALE_AUTONOMY_TERMS):
        errors.append("SCALE_OR_AUTONOMY_APPROVAL_REJECTED")
    if errors:
        return {"ok": False, "errors": errors, "written": []}

    approval = {"exact_phrase": REQUIRED_PHRASE, "operator": operator, "timestamp": expires_at, "reason": reason,
                "scope": REQUIRED_SCOPE, "expiration": expires_at, **ACKS}
    manifest = {"version": "v3", "proof_target": proof_target, "scope": REQUIRED_SCOPE, "reason": reason,
                "operator_metadata": {"operator": operator, "timestamp": expires_at}, "expiry": expires_at,
                "config_descriptors": {"live_submit": True, "caps": True}, "adapter_descriptors": {"firewall": True},
                "approvals": {"exact_phrase": REQUIRED_PHRASE, "acknowledgments": "; ".join(ACKS.values())},
                "not_self_authorized_by_dummy": True}
    live_submit = {"live_submit_enabled": True, "operator_confirmed": True, "not_self_authorized_by_dummy": True}
    caps = {"caps_confirmed": True, "strict_caps": True, "operator_confirmed": True, "not_self_authorized_by_dummy": True}
    adapter = {"firewall_adapter_injected": True, "non_broker_double": False, "operator_confirmed": True, "not_self_authorized_by_dummy": True}

    artifacts = {"authority_manifest.json": manifest, APPROVAL_FILENAME: approval,
                 "live_submit_descriptor.json": live_submit, "caps_descriptor.json": caps,
                 "firewall_adapter_descriptor.json": adapter}
    ledger = {name: _hash(data) for name, data in artifacts.items()}
    meta = {"_meta": {"not_self_authorized_by_dummy": True, "proof_target": proof_target, "scope": REQUIRED_SCOPE,
                      "expiry": expires_at, "operator": operator, "hash_ledger": ledger,
                      "market_order_permitted": False, "scale_permitted": False, "autonomy_permitted": False}}

    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, data in artifacts.items():
        payload = dict(data)
        payload.update(meta)
        (output_dir / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        written.append(str(output_dir / name))
    (output_dir / "hash_ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    written.append(str(output_dir / "hash_ledger.json"))
    return {"ok": True, "errors": [], "written": written, "hash_ledger": ledger}


def verify_authority_pack(source_dir: Path) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    missing = [n for n in PACK_FILES if not (source_dir / n).exists()]
    checks["all_artifacts_present"] = not missing
    approval = _load_json(source_dir / APPROVAL_FILENAME)
    manifest = _load_json(source_dir / "authority_manifest.json")
    checks["exact_approval_phrase"] = approval.get("exact_phrase") == REQUIRED_PHRASE
    checks["manifest_phrase_exact"] = manifest.get("approvals", {}).get("exact_phrase") == REQUIRED_PHRASE
    checks["proof_target_valid"] = manifest.get("proof_target") == REQUIRED_PROOF_TARGET
    checks["scope_valid"] = approval.get("scope") == REQUIRED_SCOPE
    checks["expiry_present"] = bool(approval.get("expiration"))
    checks["all_acks_present"] = all(approval.get(k) == v for k, v in ACKS.items())
    checks["no_market_order_permission"] = not _contains(json.dumps(manifest) + json.dumps(approval), MARKET_ALLOW_TERMS)
    checks["no_scale_autonomy_permission"] = not _contains(json.dumps(manifest) + json.dumps(approval), SCALE_AUTONOMY_TERMS)
    checks["no_broad_approval"] = not _contains(str(manifest.get("reason", "")), BROAD_TERMS)
    checks["not_self_authorized_by_dummy"] = bool(manifest.get("not_self_authorized_by_dummy"))
    # Hash verification against ledger if present.
    ledger = _load_json(source_dir / "hash_ledger.json")
    hash_ok = True
    for name, expected in ledger.items():
        data = _load_json(source_dir / name)
        data.pop("_meta", None)
        if _hash(data) != expected:
            hash_ok = False
    checks["hashes_match"] = hash_ok and bool(ledger)
    ok = all(checks.values())
    return {"ok": ok, "checks": checks, "missing": missing}


def install_authority_pack(*, source_dir: Path, operator_confirm_install: str, runtime_approvals_dir: Path) -> dict[str, Any]:
    if operator_confirm_install != INSTALL_CONFIRM_PHRASE:
        return {"ok": False, "error": "INSTALL_CONFIRMATION_NOT_EXACT", "written": []}
    verdict = verify_authority_pack(source_dir)
    if not verdict["ok"]:
        return {"ok": False, "error": "SOURCE_PACK_INVALID", "checks": verdict["checks"], "written": []}
    runtime_approvals_dir.mkdir(parents=True, exist_ok=True)
    written = []
    # Only the approval file(s) Dummy consumes are copied. Never live-submit, caps, or adapter.
    src = _load_json(source_dir / APPROVAL_FILENAME)
    src.pop("_meta", None)
    dest = runtime_approvals_dir / APPROVAL_FILENAME
    dest.write_text(json.dumps(src, indent=2), encoding="utf-8")
    written.append(str(dest))
    return {"ok": True, "written": written, "live_submit_modified": False, "caps_modified": False, "adapter_injected_by_appliance": False}


# ----------------------------- status / runners -----------------------------

def status() -> dict[str, Any]:
    v303 = _load_json(ARTIFACTS_DIR / "final_report_v303.json")
    return {
        "proof_starvation_stop_rule_active": True,
        "architecture_sprawl_blocked": v303.get("architecture_sprawl_blocked"),
        "real_proof_present": v303.get("real_proof_present"),
        "operator_execution_fork_status": _load_json(ARTIFACTS_DIR / "final_report_v296.json").get("operator_execution_fork_controller_status"),
        "command_seal_status": command_seal_status(),
        "runtime_approvals_exists": DEFAULT_RUNTIME_APPROVALS.exists(),
        "external_authority_manifest_present": bool(list(ARTIFACTS_DIR.glob("external_authority_manifest*.json"))),
        "env_gate_present": env_gate_present(),
        "live_submit_descriptor_present": (ARTIFACTS_DIR / "live_submit_descriptor.json").exists(),
        "caps_descriptor_present": (ARTIFACTS_DIR / "caps_descriptor.json").exists(),
        "firewall_adapter_descriptor_present": (ARTIFACTS_DIR / "firewall_adapter_descriptor.json").exists(),
        "proof_lock_used": proof_lock_exists(),
        "note": "Chat approval is NOT executable authority. Operator must build+install an authority pack outside Dummy.",
    }


def _default_runner(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=str(DUMMY_ROOT), capture_output=True, text=True)
    return {"cmd": " ".join(cmd), "returncode": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-500:]}


def dry_run_all(runner: Callable[[list[str]], dict[str, Any]] = _default_runner) -> dict[str, Any]:
    results = [runner(cmd) for cmd in READONLY_CMDS]
    return {"ran": [r["cmd"] for r in results], "execute_once_called": False, "broker_contacted": False, "results": results}


def run_authority_checks(runner: Callable[[list[str]], dict[str, Any]] = _default_runner) -> dict[str, Any]:
    results = [runner(cmd) for cmd in AUTHORITY_CHECK_CMDS]
    seal = command_seal_status()
    guidance = "COMMAND_SEAL_READY_ENV_GATE_REQUIRED" if seal == "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT" and not env_gate_present() else seal
    return {"ran": [r["cmd"] for r in results], "execute_once_called": False, "command_seal_status": seal, "guidance": guidance}


def run_live_proof_once(*, runner: Callable[[list[str]], dict[str, Any]] = _default_runner,
                        env: dict[str, str] | None = None, seal_status: str | None = None,
                        proof_lock: bool | None = None) -> dict[str, Any]:
    seal_status = seal_status if seal_status is not None else command_seal_status()
    proof_lock = proof_lock if proof_lock is not None else proof_lock_exists()
    if not env_gate_present(env):
        return {"verdict": "BLOCKED_ENV_GATE_ABSENT", "execute_once_called": False, "required_env": [f"{ENV_MODE[0]}={ENV_MODE[1]}", f"{ENV_ACK[0]}={ENV_ACK[1]}"]}
    if seal_status != "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT":
        return {"verdict": "BLOCKED_COMMAND_SEAL_NOT_READY", "execute_once_called": False, "command_seal_status": seal_status}
    if proof_lock:
        return {"verdict": "BLOCKED_PROOF_LOCK_ALREADY_USED", "execute_once_called": False}
    exec_result = runner(EXECUTE_ONCE_CMD)
    post = [runner(cmd) for cmd in POST_PROOF_CMDS]
    return {"verdict": "EXECUTE_ONCE_INVOKED_THEN_POST_PROOF", "execute_once_called": True,
            "execute_once": exec_result, "post_proof": [r["cmd"] for r in post],
            "proof_paths": [str(ARTIFACTS_DIR / "final_report_v298.json"), str(ARTIFACTS_DIR / "final_report_v300.json"), str(ARTIFACTS_DIR / "final_report_v301.json")]}


# ----------------------------- CLI -----------------------------

def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="External operator-side authority appliance for Dummy live-proof (fail-closed).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")
    sub.add_parser("init-templates")
    sub.add_parser("print-runbook")
    sub.add_parser("dry-run-all")
    sub.add_parser("run-authority-checks")
    sub.add_parser("run-live-proof-once")

    b = sub.add_parser("build-authority-pack")
    b.add_argument("--output", required=True)
    b.add_argument("--operator", required=True)
    b.add_argument("--reason", required=True)
    b.add_argument("--expires-at", required=True)
    b.add_argument("--proof-target", required=True)
    b.add_argument("--typed-approval", required=True)
    b.add_argument("--acknowledge-risk", required=True)

    v = sub.add_parser("verify-authority-pack")
    v.add_argument("--source", required=True)

    i = sub.add_parser("install-authority-pack")
    i.add_argument("--source", required=True)
    i.add_argument("--operator-confirm-install", required=True)
    i.add_argument("--runtime-approvals-dir", default=str(DEFAULT_RUNTIME_APPROVALS))

    args = parser.parse_args(argv)

    if args.command == "status":
        _print(status())
    elif args.command == "init-templates":
        _print({"written": init_templates()})
    elif args.command == "print-runbook":
        print("# DUMMY live-proof gated runbook (run ONLY after operator authority + env gate exist)")
        print(f"# env gate: {ENV_MODE[0]}={ENV_MODE[1]}  {ENV_ACK[0]}={ENV_ACK[1]}")
        for step, cmd in enumerate(RUNBOOK, 1):
            print(f"{step}. {cmd}")
        print("# STOP after step 4 auto-locks. Hard max ONE attempt. Do NOT repeat.")
    elif args.command == "dry-run-all":
        _print(dry_run_all())
    elif args.command == "run-authority-checks":
        _print(run_authority_checks())
    elif args.command == "run-live-proof-once":
        _print(run_live_proof_once())
    elif args.command == "build-authority-pack":
        result = build_authority_pack(output_dir=Path(args.output), operator=args.operator, reason=args.reason,
                                      expires_at=args.expires_at, proof_target=args.proof_target,
                                      typed_approval=args.typed_approval, acknowledge_risk=args.acknowledge_risk)
        _print(result)
        return 0 if result["ok"] else 2
    elif args.command == "verify-authority-pack":
        result = verify_authority_pack(Path(args.source))
        _print(result)
        return 0 if result["ok"] else 2
    elif args.command == "install-authority-pack":
        result = install_authority_pack(source_dir=Path(args.source), operator_confirm_install=args.operator_confirm_install,
                                        runtime_approvals_dir=Path(args.runtime_approvals_dir))
        _print(result)
        return 0 if result["ok"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
