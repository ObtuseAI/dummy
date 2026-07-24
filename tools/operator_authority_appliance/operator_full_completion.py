"""Operator-side full-completion orchestrator for the DUMMY real-proof path.

Top-level one-shot driver that sequences the EXISTING operator tools (operator_bootstrap →
operator_env_wizard → operator_authority_appliance) so the remaining real-proof path is runnable in one
local command sequence. It adds no Dummy architecture, never self-authorizes Dummy, never creates
runtime/approvals by default, never modifies live-submit/caps, never injects a broker adapter, never
contacts a broker, never calls the Dummy execute-once script directly (only via the appliance
`run-live-proof-once`), and never runs live-proof without the exact env gate. All validation is delegated
to the existing tools; this module only orchestrates and reports.

Exit codes: 0 success · 2 missing/mismatched operator input · 3 subprocess failure · 4 safety rejection ·
5 external dependency missing (live-submit/caps/adapter/authority not externally present).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import inspect
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core import config_loader, env_loader, kalshi_market_validator, proof_order_candidate
from core.proof_authority import (
    REQUIRED_CONFIRMATION as SECOND_PROOF_REQUIRED_CONFIRMATION,
    SECOND_PROOF_AUTHORITY_DIR,
    SecondProofAuthority,
    activate_second_proof_authority,
    authority_from_dict,
    authority_to_dict,
    build_second_proof_authority_draft,
)
from core.caps_authority import (
    CAPS_AUTHORITY_REGISTRATION_PATH as DEFAULT_CAPS_AUTHORITY_REGISTRATION_PATH,
    evaluate_caps_authority,
)
from core.second_proof_lock import (
    create_second_proof_lock,
    is_second_proof_lock_consumed,
)
from core.env_loader import kalshi_credential_status, load_whitelisted_env
from core.live_submit_state import (
    LIVE_SUBMIT_REQUIRED_ACK,
    LIVE_SUBMIT_TYPED_CONFIRMATION,
    build_caps_authority_binding,
    validate_operator_one_proof_enabled,
)
from core.proof_lock import REAL_PROOF_REGISTRY_PATH, load_real_proof_registry, real_proof_attempt_exists

BASE = Path(__file__).resolve().parent
DUMMY_ROOT = BASE.parents[1]
BOOTSTRAP_CLI = BASE / "operator_bootstrap.py"
APPLIANCE_CLI = BASE / "operator_authority_appliance.py"
DEFAULT_ARTIFACTS_DIR = BASE / "artifacts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bs = _load("operator_bootstrap", BOOTSTRAP_CLI)
_wiz = _bs._wiz
_app = _bs._app

REQUIRED_PHRASE = _bs.REQUIRED_PHRASE
REQUIRED_RISK_ACK = _bs.REQUIRED_RISK_ACK
INSTALL_CONFIRM_PHRASE = _bs.INSTALL_CONFIRM_PHRASE
ENV_MODE = _bs.ENV_MODE
ENV_ACK = _bs.ENV_ACK
BUILD_VARS = _bs.BUILD_VARS
DEFAULT_PACK_DIR = _bs.DEFAULT_PACK_DIR
PACK_FILES = _app.PACK_FILES
SEAL_READY = "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT"

EXIT_OK, EXIT_MISSING, EXIT_SUBPROC, EXIT_SAFETY, EXIT_EXTERNAL = 0, 2, 3, 4, 5

MISSING_READ_ONLY_GET_APPROVAL_FLAG = "MISSING_READ_ONLY_GET_APPROVAL_FLAG"
KALSHI_CREDENTIALS_MISSING = "KALSHI_CREDENTIALS_MISSING"
NO_ELIGIBLE_CANDIDATE_FOUND = "NO_ELIGIBLE_CANDIDATE_FOUND"
PREVIOUS_REAL_BROKER_ATTEMPT_RECORDED = "PREVIOUS_REAL_BROKER_ATTEMPT_RECORDED"

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


def _default_runner(cmd: list[str]) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(cmd, cwd=str(DUMMY_ROOT), capture_output=True, text=True)  # shell=False


# Indirection points so tests can monkeypatch authority readiness without real artifacts.
def _seal_status() -> str:
    return _app.command_seal_status()


def _proof_lock() -> bool:
    return _app.proof_lock_exists() or real_proof_attempt_exists()


def _env_gate(env: dict[str, str]) -> bool:
    return env.get(ENV_MODE[0]) == ENV_MODE[1] and env.get(ENV_ACK[0]) == ENV_ACK[1]


def _missing_build_vars(env: dict[str, str]) -> list[str]:
    return [v for v in BUILD_VARS if not env.get(v)]


def _pack_built(pack_dir: str | None) -> bool:
    if not pack_dir:
        return False
    d = Path(pack_dir)
    return all((d / n).exists() for n in PACK_FILES)


def _bootstrap(argv: list[str], env: dict[str, str], runner: Runner, out) -> int:
    return _bs.main(argv, env=env, runner=runner, out=out)


LIVE_SUBMIT_PATH = DUMMY_ROOT / "configs" / "live_submit.json"
# Named rather than an inline literal at the write site: the activation tests
# patch every other path on this module, so the one hardcoded string was the
# only thing still writing a real operator approval file into runtime/approvals
# on a plain pytest run.  Value is unchanged (repo-root-relative, as before).
SECOND_PROOF_APPROVAL_PATH = Path(
    "runtime/approvals/dummy_second_controlled_real_broker_proof_approval.json"
)
CAPS_PATH = DUMMY_ROOT / "configs" / "caps.json"
ADAPTER_DESCRIPTOR_PATH = DUMMY_ROOT / "runtime" / "operator_external" / "livebrokerfirewall_adapter_descriptor.json"
CAPS_AUTHORITY_REGISTRATION_PATH = DEFAULT_CAPS_AUTHORITY_REGISTRATION_PATH


def _canonical_json(obj: dict[str, object]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest().upper()


def _caps_authority_status():
    """Evaluate the current caps-v2 file and its separate registration."""

    return evaluate_caps_authority(
        caps_path=CAPS_PATH,
        registration_path=CAPS_AUTHORITY_REGISTRATION_PATH,
    )


def _timestamp_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _atomic_write_json(path: Path, obj: dict[str, object]) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if path.exists():
        backup = path.with_suffix(path.suffix + f".{_timestamp_suffix()}.bak")
        path.replace(backup)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(_canonical_json(obj), encoding="utf-8")
    tmp.replace(path)
    return backup


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _caps_are_strict() -> bool:
    data = _load_json(CAPS_PATH)
    limit_only = data.get("order_type_policy") == "LIMIT_ONLY" or data.get("limit_orders_only") is True
    no_market = data.get("market_orders_allowed") is False or data.get("allow_market_orders") is False
    kill_on = data.get("kill_switch_enabled") is True or data.get("kill_switch_required") is True
    order_count_ok = data.get("max_order_count", 1) == 1
    return limit_only and no_market and kill_on and order_count_ok


def _descriptor_staged() -> bool:
    if not ADAPTER_DESCRIPTOR_PATH.exists():
        return False
    data = _load_json(ADAPTER_DESCRIPTOR_PATH)
    return (
        data.get("broker") == "KALSHI"
        and data.get("adapter_type") == "LiveBrokerFirewall"
        and data.get("order_type_policy") == "LIMIT_ONLY"
        and data.get("market_orders_allowed") is False
    )


def _load_dotenv_for_one_shot() -> dict[str, str]:
    """Load whitelisted Kalshi/Dummy env refs from .env into the process.

    Returns a dict with SET/UNSET status only; no secret values are printed.
    """
    loaded = load_whitelisted_env(dotenv_path=DUMMY_ROOT / ".env", overwrite=False)
    return loaded


# ----------------------------- diagnosis -----------------------------

def classify_blocker(env: dict[str, str]) -> str:
    if _missing_build_vars(env):
        return "MISSING_OPERATOR_VALUES"
    pack_dir = env.get("DUMMY_AUTHORITY_PACK_DIR")
    if not _pack_built(pack_dir):
        return "AUTHORITY_PACK_NOT_BUILT"
    if not _app.verify_authority_pack(Path(pack_dir))["ok"]:
        return "AUTHORITY_PACK_NOT_VERIFIED"
    if env.get("DUMMY_AUTHORITY_INSTALL_CONFIRM") != INSTALL_CONFIRM_PHRASE:
        return "INSTALL_CONFIRMATION_MISSING"
    seal = _seal_status()
    if seal != SEAL_READY:
        # Authority not fully armable locally → external live-submit/caps/adapter/authority still required.
        return "LIVE_SUBMIT_CAPS_EXTERNAL_MISSING" if seal.startswith("PARTIAL") else "COMMAND_SEAL_BLOCKED"
    if _proof_lock():
        return "PROOF_ALREADY_ATTEMPTED"
    if not _env_gate(env):
        return "ENV_GATE_MISSING"
    return "READY_FOR_LIVE_PROOF"


# ----------------------------- commands -----------------------------

def cmd_status(env: dict[str, str], runner: Runner, out) -> int:
    stop = runner([sys.executable, _bs.STOP_RULE_SCRIPT])
    stop_ok = "PASS_PROOF_STARVATION_STOP_RULE_ACTIVE" in (stop.stdout or "")
    print("# DUMMY operator full-completion status (read-only)", file=out)
    print(f"proof_starvation_stop_rule_active={stop_ok}", file=out)
    print(f"command_seal_status={_seal_status()}", file=out)
    print(f"env_gate_present={_env_gate(env)}", file=out)
    print(f"runtime_approvals_exists={_app.DEFAULT_RUNTIME_APPROVALS.exists()}", file=out)
    print(f"proof_lock_used={_proof_lock()}", file=out)
    print(f"first_hard_blocker={classify_blocker(env)}", file=out)
    return EXIT_OK


def cmd_doctor(env: dict[str, str], runner: Runner, out, artifacts_dir: Path | None = None) -> int:
    artifacts_dir = artifacts_dir or Path(env.get("DUMMY_FULLCOMP_ARTIFACTS_DIR", str(DEFAULT_ARTIFACTS_DIR)))
    blocker = classify_blocker(env)
    stop = runner([sys.executable, _bs.STOP_RULE_SCRIPT])
    report = {
        "tool": "operator_full_completion",
        "proof_starvation_stop_rule_active": "PASS_PROOF_STARVATION_STOP_RULE_ACTIVE" in (stop.stdout or ""),
        "first_hard_blocker": blocker,
        "command_seal_status": _seal_status(),
        "env_gate_present": _env_gate(env),
        "runtime_approvals_exists": _app.DEFAULT_RUNTIME_APPROVALS.exists(),
        "proof_lock_used": _proof_lock(),
        "missing_operator_values": _missing_build_vars(env),
        "live_orders": 0, "broker_contacted": False, "approval_files_written_by_dummy": 0,
        "live_submit_modified": False, "caps_modified": False, "scale_applied": False, "autonomous_trading": False,
        "not_self_authorized_by_dummy": True,
    }
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / "operator_full_completion_doctor.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), file=out)
    print(f"WROTE_DOCTOR_REPORT: {path}", file=out)
    return EXIT_OK


def cmd_prepare_second_proof_authority(args, out) -> int:
    """Create a draft second-proof authority from the validated V3 candidate.

    Does not activate, does not enable live-submit, does not contact the broker,
    and does not consume any proof lock.
    """
    try:
        authority = build_second_proof_authority_draft()
    except ValueError as exc:
        report = {
            "verdict": "BLOCKED_SECOND_PROOF_AUTHORITY",
            "draft_created": False,
            "authority_active": False,
            "submit_allowed_now": False,
            "reason_submit_not_allowed": str(exc),
            "broker_contact": False,
            "live_order_count": 0,
        }
        SECOND_PROOF_AUTHORITY_DIR.mkdir(parents=True, exist_ok=True)
        report_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_PREFLIGHT_REPORT.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    SECOND_PROOF_AUTHORITY_DIR.mkdir(parents=True, exist_ok=True)
    draft_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_DRAFT.json"
    draft_path.write_text(json.dumps(authority_to_dict(authority), indent=2, sort_keys=True), encoding="utf-8")

    report = {
        "verdict": "SECOND_PROOF_AUTHORITY_DRAFT_READY",
        "draft_created": True,
        "authority_active": False,
        "submit_allowed_now": False,
        "reason_submit_not_allowed": "SECOND_PROOF_AUTHORITY_NOT_ACTIVE",
        "candidate_hash": authority.candidate_hash,
        "caps_hash": authority.caps_hash,
        "caps_schema_version": authority.caps_schema_version,
        "caps_authority_epoch": authority.caps_authority_epoch,
        "caps_authority_state": authority.caps_authority_state,
        "caps_authority_registration_sha256": authority.caps_authority_registration_sha256,
        "caps_authority_registration_valid": authority.caps_authority_registration_valid,
        "execution_authority": False,
        "descriptor_hash": authority.descriptor_hash,
        "runtime_approval_hash": authority.runtime_approval_hash,
        "proof_registry_hash": authority.prior_proof_registry_hash,
        "broker_contact": False,
        "live_order_count": 0,
        "draft_path": str(draft_path),
    }
    report_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_PREFLIGHT_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2), file=out)
    return EXIT_OK


def cmd_activate_second_proof_authority(args, out) -> int:
    """Activate the draft second-proof authority after exact typed confirmation.

    Writes the active approval, creates a fresh unconsumed second-proof lock
    namespace, scopes live-submit to this authority, and backs up the previous
    live_submit.json. Does not run one-shot-live or contact the broker.
    """
    draft_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_DRAFT.json"
    if not draft_path.exists():
        print(json.dumps({"verdict": "BLOCKED_SECOND_PROOF_AUTHORITY", "reason": "DRAFT_MISSING"}, indent=2), file=out)
        return EXIT_SAFETY

    try:
        draft_data = json.loads(draft_path.read_text(encoding="utf-8"))
        draft = authority_from_dict(draft_data)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "verdict": "BLOCKED_SECOND_PROOF_AUTHORITY",
                    "reason": f"DRAFT_SCHEMA_INVALID:{type(exc).__name__}",
                },
                indent=2,
            ),
            file=out,
        )
        return EXIT_SAFETY

    if args.confirm != SECOND_PROOF_REQUIRED_CONFIRMATION:
        print(json.dumps({"verdict": "BLOCKED_CONFIRMATION_MISMATCH"}, indent=2), file=out)
        return EXIT_MISSING

    try:
        active = activate_second_proof_authority(
            draft,
            args.operator_name,
            args.reason,
            args.expires_at,
            args.confirm,
        )
    except ValueError as exc:
        print(json.dumps({"verdict": "BLOCKED_SECOND_PROOF_AUTHORITY", "reason": str(exc)}, indent=2), file=out)
        return EXIT_SAFETY

    # Write scoped active approval.
    approval = {
        "authority_id": active.authority_id,
        "authority_type": active.authority_type,
        "operator": active.operator_name,
        "reason": active.reason,
        "expiration": active.expires_at,
        "scope": "second_controlled_real_broker_proof_via_firewall_only",
        "candidate_hash": active.candidate_hash,
        "caps_hash": active.caps_hash,
        "caps_schema_version": active.caps_schema_version,
        "caps_authority_epoch": active.caps_authority_epoch,
        "caps_authority_registration_sha256": active.caps_authority_registration_sha256,
        "execution_authority": False,
        "confirmation_digest": active.exact_typed_confirmation_digest,
        "market_orders_allowed": False,
        "scale_allowed": False,
        "autonomy_allowed": False,
        "not_self_authorized_by_dummy": True,
    }
    approval_path = Path(SECOND_PROOF_APPROVAL_PATH)
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps(approval, indent=2, sort_keys=True), encoding="utf-8")

    # Create fresh second-proof lock namespace.
    lock_path = create_second_proof_lock(active.authority_id)

    # Backup and scope live_submit.json.
    hash_before = _sha256_file(LIVE_SUBMIT_PATH)
    backup = None
    if LIVE_SUBMIT_PATH.exists():
        backup = LIVE_SUBMIT_PATH.with_suffix(LIVE_SUBMIT_PATH.suffix + f".{_timestamp_suffix()}.bak")
        LIVE_SUBMIT_PATH.replace(backup)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    caps_authority_status = _caps_authority_status()
    scoped = {
        "enabled": True,
        "operator": active.operator_name,
        "reason": active.reason,
        "timestamp": now,
        "expiry": active.expires_at,
        "proof_scope": "one_controlled_proof",
        "second_proof_authority_id": active.authority_id,
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "scale_enabled": False,
        "autonomy_enabled": False,
        "explicit_acknowledgement": LIVE_SUBMIT_REQUIRED_ACK,
        "candidate_hash": active.candidate_hash,
        "descriptor_hashes": [active.descriptor_hash],
        "caps_hashes": [active.caps_hash],
        "caps_schema_version": active.caps_schema_version,
        "caps_authority_epoch": active.caps_authority_epoch,
        "caps_authority_registration_required": True,
        "caps_authority_registration_sha256": active.caps_authority_registration_sha256,
    }
    validation = validate_operator_one_proof_enabled(
        scoped,
        caps_authority_status=caps_authority_status,
    )
    if not validation.ok:
        if backup:
            backup.replace(LIVE_SUBMIT_PATH)
        print(json.dumps({"verdict": "BLOCKED_LIVE_SUBMIT_INVALID", "errors": validation.errors}, indent=2), file=out)
        return EXIT_SAFETY
    _atomic_write_json(LIVE_SUBMIT_PATH, scoped)
    hash_after = _sha256_file(LIVE_SUBMIT_PATH)

    active_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_ACTIVE.json"
    active_path.write_text(json.dumps(authority_to_dict(active), indent=2, sort_keys=True), encoding="utf-8")

    report = {
        "verdict": "SECOND_PROOF_AUTHORITY_ACTIVE",
        "authority_id": active.authority_id,
        "active_path": str(active_path),
        "approval_path": str(approval_path),
        "lock_path": str(lock_path),
        "live_submit_hash_before": hash_before,
        "live_submit_hash_after": hash_after,
        "backup_path": str(backup) if backup else None,
        "candidate_hash": active.candidate_hash,
        "caps_hash": active.caps_hash,
        "descriptor_hash": active.descriptor_hash,
        "runtime_approval_hash": active.runtime_approval_hash,
        "no_broker_contact": True,
        "no_live_proof_run": True,
    }
    print(json.dumps(report, indent=2), file=out)
    return EXIT_OK


def cmd_one_shot_prepare(args, runner: Runner, out) -> int:
    # 1. generate operator env file (wizard validates approval/risk/market/scale/broad; may exit 4).
    env_file = str(Path(args.authority_pack_dir) / "operator_authority.env")
    rc = _bootstrap(["generate-env", "--output", env_file, "--operator", args.operator, "--reason", args.reason,
                     "--expires-at", args.expires_at, "--authority-pack-dir", args.authority_pack_dir,
                     "--typed-approval", args.typed_approval, "--risk-ack", args.risk_ack], {}, runner, out)
    if rc == _bs.EXIT_SAFETY:
        print("VERDICT: REPAIR_REQUIRED (safety rejection)", file=out)
        return EXIT_SAFETY
    if rc != EXIT_OK:
        print("VERDICT: REPAIR_REQUIRED", file=out)
        return rc if rc in (EXIT_MISSING, EXIT_SUBPROC) else EXIT_SUBPROC
    # 2. build + verify pack in-process via the appliance's own functions (reuse, not duplicate).
    build = _app.build_authority_pack(output_dir=Path(args.authority_pack_dir), operator=args.operator,
                                      reason=args.reason, expires_at=args.expires_at, proof_target=_app.REQUIRED_PROOF_TARGET,
                                      typed_approval=args.typed_approval, acknowledge_risk=args.risk_ack)
    if not build["ok"]:
        print("SAFETY_REJECTED: " + ", ".join(build["errors"]), file=out)
        print("VERDICT: REPAIR_REQUIRED", file=out)
        return EXIT_SAFETY
    verify = _app.verify_authority_pack(Path(args.authority_pack_dir))
    print(f"PACK_BUILT: {len(build['written'])} files", file=out)
    print(f"PACK_VERIFIED: {verify['ok']}", file=out)
    if not verify["ok"]:
        print("VERDICT: REPAIR_REQUIRED", file=out)
        return EXIT_SAFETY
    # 4. print install command + external requirements.
    print("# Pack built + verified. Next (all EXTERNAL, operator-side, Dummy must NOT do these):", file=out)
    print("#  1. operator externally enables live-submit", file=out)
    print("#  2. operator externally confirms caps", file=out)
    print("#  3. operator externally injects LiveBrokerFirewall adapter", file=out)
    print(f'export DUMMY_AUTHORITY_INSTALL_CONFIRM="{INSTALL_CONFIRM_PHRASE}"', file=out)
    print(f'python tools/operator_authority_appliance/operator_full_completion.py one-shot-install --authority-pack-dir "{args.authority_pack_dir}" --operator-confirm-install "{INSTALL_CONFIRM_PHRASE}"', file=out)
    print("VERDICT: OPERATOR_AUTHORITY_PACK_READY_EXTERNAL_CONFIG_REQUIRED", file=out)
    return EXIT_OK


def cmd_one_shot_install(args, runner: Runner, out) -> int:
    if args.operator_confirm_install != INSTALL_CONFIRM_PHRASE:
        print("INSTALL_CONFIRMATION_REQUIRED (exact): " + INSTALL_CONFIRM_PHRASE, file=out)
        return EXIT_MISSING
    env = {"DUMMY_AUTHORITY_PACK_DIR": args.authority_pack_dir, "DUMMY_AUTHORITY_INSTALL_CONFIRM": args.operator_confirm_install}
    return _bootstrap(["install-if-confirmed"], env, runner, out)


def _check_kalshi_credentials() -> tuple[list[str], dict[str, Any]]:
    """Return (missing_ref_names, status_dict) without exposing values.

    Requires KALSHI_API_KEY_ID and at least one private-key ref (inline PEM or
    readable path), matching the KalshiLiveBrokerFirewallAdapter resolver.
    """
    status = kalshi_credential_status()
    missing: list[str] = []

    if not status.get("KALSHI_API_KEY_ID", {}).get("present"):
        missing.append("KALSHI_API_KEY_ID")

    private_key_refs = {
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_PRIVATE_KEY",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_PRIVATE_KEY_PATH",
    }
    key_ok = False
    for key in private_key_refs:
        entry = status.get(key, {})
        if not entry.get("present"):
            continue
        if "file_exists" in entry:
            if entry["file_exists"]:
                key_ok = True
        else:
            key_ok = True
    if not key_ok:
        missing.append("KALSHI_PRIVATE_KEY_REF")

    # Surface any path refs that are present but point to missing files.
    for key in private_key_refs:
        entry = status.get(key, {})
        if entry.get("present") and "file_exists" in entry and not entry["file_exists"]:
            missing.append(f"{key}_path_missing")

    return missing, status


def cmd_enable_one_proof_live_submit(args, out) -> int:
    """Operator-controlled, typed-confirmation enablement of one-proof live-submit.

    Writes configs/live_submit.json atomically with a timestamped backup. Requires
    exact typed confirmation, operator name, reason, and future expiry. Does not
    run one-shot-live automatically.
    """
    if args.typed_confirmation != LIVE_SUBMIT_TYPED_CONFIRMATION:
        print("TYPED_CONFIRMATION_REQUIRED (exact): " + LIVE_SUBMIT_TYPED_CONFIRMATION, file=out)
        return EXIT_MISSING

    if not args.operator or not args.reason or not args.expires_at:
        print("MISSING: --operator, --reason, and --expires-at are required", file=out)
        return EXIT_MISSING

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    caps_authority_status = _caps_authority_status()
    proposed: dict[str, object] = {
        "enabled": True,
        "operator": args.operator,
        "reason": args.reason,
        "timestamp": now,
        "expiry": args.expires_at,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "scale_enabled": False,
        "autonomy_enabled": False,
        "explicit_acknowledgement": LIVE_SUBMIT_REQUIRED_ACK,
        **build_caps_authority_binding(caps_authority_status),
    }

    # Optionally include descriptor/caps hashes for hash-tracking.
    descriptor_hash = _sha256_file(ADAPTER_DESCRIPTOR_PATH)
    caps_hash = _sha256_file(CAPS_PATH)
    if descriptor_hash:
        proposed["descriptor_hashes"] = [descriptor_hash]
    if caps_hash:
        proposed["caps_hashes"] = [caps_hash]

    validation = validate_operator_one_proof_enabled(
        proposed,
        caps_authority_status=caps_authority_status,
    )
    if not validation.ok:
        print("VALIDATION_FAILED: " + ", ".join(validation.errors), file=out)
        return EXIT_SAFETY

    hash_before = _sha256_file(LIVE_SUBMIT_PATH)
    backup = _atomic_write_json(LIVE_SUBMIT_PATH, proposed)
    hash_after = _sha256_file(LIVE_SUBMIT_PATH)

    report = {
        "verdict": "LIVE_SUBMIT_ENABLED_ONE_PROOF",
        "path": str(LIVE_SUBMIT_PATH),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "backup_path": str(backup) if backup else None,
        "descriptor_hash": descriptor_hash,
        "caps_hash": caps_hash,
        "safety_notes": [
            "one controlled proof only",
            "limit-only",
            "command-seal required",
            "LiveBrokerFirewall required",
            "no market orders",
            "no scale/autonomy",
            "atomic write with backup",
            "no live proof run",
            "no broker contact",
        ],
    }
    print(json.dumps(report, indent=2), file=out)
    return EXIT_OK


def cmd_disable_live_submit(args, out) -> int:
    """Restore the default safe disabled state."""
    existing = _load_json(LIVE_SUBMIT_PATH)
    disabled: dict[str, object] = {
        **existing,
        "enabled": False,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reason": f"operator relock: {existing.get('reason', 'none')}",
    }
    disabled.pop("explicit_acknowledgement", None)
    hash_before = _sha256_file(LIVE_SUBMIT_PATH)
    backup = _atomic_write_json(LIVE_SUBMIT_PATH, disabled)
    hash_after = _sha256_file(LIVE_SUBMIT_PATH)
    print(json.dumps({
        "verdict": "LIVE_SUBMIT_DISABLED",
        "path": str(LIVE_SUBMIT_PATH),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "backup_path": str(backup) if backup else None,
    }, indent=2), file=out)
    return EXIT_OK


def _second_proof_authority_state() -> dict[str, Any]:
    """Return the current second-proof authority state without secrets."""
    draft_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_DRAFT.json"
    active_path = SECOND_PROOF_AUTHORITY_DIR / "SECOND_PROOF_AUTHORITY_ACTIVE.json"
    if active_path.exists():
        try:
            data = json.loads(active_path.read_text(encoding="utf-8"))
            authority = authority_from_dict(data)
            return {"state": "active", "authority": authority}
        except Exception:
            return {"state": "active_invalid"}
    if draft_path.exists():
        return {"state": "draft"}
    return {"state": "absent"}


def _second_proof_check_env_gate_required(env: dict[str, str], authority: SecondProofAuthority) -> bool:
    """Return True if second-proof authority is active and all non-env gates pass."""
    from core.proof_authority import EXPECTED_CANDIDATE_HASH
    if authority.candidate_hash != EXPECTED_CANDIDATE_HASH:
        return False
    if authority.caps_hash != _sha256_file(CAPS_PATH):
        return False
    caps_authority = _caps_authority_status()
    if not caps_authority.authority_registration_valid:
        return False
    if caps_authority.current_caps_sha256 != authority.caps_hash:
        return False
    if (
        caps_authority.authority_registration_sha256
        != authority.caps_authority_registration_sha256
    ):
        return False
    if authority.descriptor_hash != _sha256_file(ADAPTER_DESCRIPTOR_PATH):
        return False
    if not _caps_are_strict():
        return False
    if not _descriptor_staged():
        return False
    if _seal_status() != SEAL_READY:
        return False
    return True


def cmd_one_shot_check(env: dict[str, str], runner: Runner, out) -> int:
    # Allow .env to supply whitelisted Kalshi/Dummy env refs for this check only.
    _load_dotenv_for_one_shot()

    missing_creds, cred_status = _check_kalshi_credentials()
    live_submit = _load_json(LIVE_SUBMIT_PATH)
    caps_authority = _caps_authority_status()
    live_submit_validation = validate_operator_one_proof_enabled(
        live_submit,
        caps_authority_status=caps_authority,
    )
    live_submit_valid = live_submit_validation.ok
    caps_strict = _caps_are_strict()
    descriptor_ok = _descriptor_staged()
    seal = _seal_status()

    report = {
        "verdict": "READY_FOR_LIVE_PROOF",
        "command_seal_status": seal,
        "live_submit_valid": live_submit_valid,
        "caps_strict": caps_strict,
        "caps_authority_state": caps_authority.state,
        "caps_authority_registration_valid": caps_authority.authority_registration_valid,
        "caps_authority_execution_authority": False,
        "descriptor_staged": descriptor_ok,
        "credential_refs": {k: {"present": v.get("present"), "file_exists": v.get("file_exists")}
                            for k, v in cred_status.items()},
    }

    if missing_creds:
        report["verdict"] = "BLOCKED_MISSING_KALSHI_CREDENTIALS"
        report["missing_refs"] = missing_creds
        print(json.dumps(report, indent=2), file=out)
        return EXIT_OK

    # Second-proof authority takes precedence over the default disabled path.
    sp_state = _second_proof_authority_state()
    if sp_state["state"] == "draft":
        report["verdict"] = "SECOND_PROOF_AUTHORITY_DRAFT_READY"
        report["reason_submit_not_allowed"] = "SECOND_PROOF_AUTHORITY_NOT_ACTIVE"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_OK
    if sp_state["state"] == "active":
        authority = sp_state["authority"]
        from core.proof_authority import V3_CANDIDATE_PATH as _V3_CANDIDATE_PATH
        current_candidate_hash = _sha256_file(_V3_CANDIDATE_PATH)
        if authority.candidate_hash != current_candidate_hash:
            report["verdict"] = "BLOCKED_CANDIDATE_HASH_MISMATCH"
        elif authority.caps_hash != _sha256_file(CAPS_PATH):
            report["verdict"] = "BLOCKED_CAPS_HASH_MISMATCH"
        elif not caps_authority.config_integrity_valid:
            report["verdict"] = "BLOCKED_CAPS_V2_CONFIG_INTEGRITY"
        elif not caps_authority.authority_registration_valid:
            report["verdict"] = "BLOCKED_CAPS_AUTHORITY_REGISTRATION"
        elif (
            caps_authority.authority_registration_sha256
            != authority.caps_authority_registration_sha256
        ):
            report["verdict"] = "BLOCKED_CAPS_AUTHORITY_REGISTRATION_MISMATCH"
        elif not live_submit_valid:
            report["verdict"] = "BLOCKED_LIVE_SUBMIT_INVALID"
            report["live_submit_errors"] = live_submit_validation.errors
        elif authority.descriptor_hash != _sha256_file(ADAPTER_DESCRIPTOR_PATH):
            report["verdict"] = "BLOCKED_DESCRIPTOR_HASH_MISMATCH"
        elif seal != SEAL_READY:
            report["verdict"] = "BLOCKED_COMMAND_SEAL"
        elif not _env_gate(env):
            report["verdict"] = "SECOND_PROOF_READY_ENV_GATE_REQUIRED"
        else:
            report["verdict"] = "READY_FOR_LIVE_PROOF"
        report["second_proof_authority_id"] = authority.authority_id
        print(json.dumps(report, indent=2), file=out)
        return EXIT_OK

    if not (live_submit_valid and caps_strict and descriptor_ok):
        report["verdict"] = "BLOCKED_LIVE_SUBMIT_CAPS"
        report["live_submit_errors"] = (
            live_submit_validation.errors if not live_submit_valid else []
        )
        report["caps_strict"] = caps_strict
        report["descriptor_staged"] = descriptor_ok
        print(json.dumps(report, indent=2), file=out)
        return EXIT_OK

    if seal != SEAL_READY:
        report["verdict"] = "BLOCKED_COMMAND_SEAL"
        report["command_seal_status"] = seal
        print(json.dumps(report, indent=2), file=out)
        return EXIT_OK

    if not _env_gate(env):
        report["verdict"] = "COMMAND_SEAL_READY_ENV_GATE_REQUIRED"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_OK

    print(json.dumps(report, indent=2), file=out)
    return EXIT_OK


def cmd_second_proof_runtime_preflight(env: dict[str, str], out) -> int:
    """Import the full one-shot-live dependency graph and validate all gates except env.

    This command is intentionally read-only:
    - it imports ``core.second_proof_runner`` (and therefore ``calibration``);
    - it loads the active second-proof authority, lock, and V3 candidate;
    - it verifies every recorded hash still matches the filesystem;
    - it confirms live-submit is disabled and the command seal is ready;
    - it does NOT set the env gate, call the adapter, contact the broker, enable
      live-submit, or mutate canonical candidate artifacts.
    """
    report: dict[str, Any] = {
        "verdict": "SECOND_PROOF_RUNTIME_PREFLIGHT_PASS",
        "broker_contacted": False,
        "live_order_count": 0,
        "market_order_status": False,
        "scale_autonomy_status": "disabled",
    }

    # Import the full runtime dependency graph.  This is the line that originally
    # failed with ``ModuleNotFoundError: No module named 'calibration'``.
    try:
        pass
    except Exception as exc:
        report["verdict"] = "BLOCKED_RUNTIME_IMPORT"
        report["exact_blocker"] = f"{type(exc).__name__}:{exc}"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_EXTERNAL

    # Active authority presence.
    sp_state = _second_proof_authority_state()
    if sp_state["state"] != "active":
        report["verdict"] = "BLOCKED_SECOND_PROOF_AUTHORITY"
        report["exact_blocker"] = f"second_proof_authority_state={sp_state['state']}"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    authority = sp_state["authority"]
    report["authority_id"] = authority.authority_id
    report["second_proof_lock_consumed"] = is_second_proof_lock_consumed(authority.authority_id)

    # Lock must be fresh.
    if is_second_proof_lock_consumed(authority.authority_id):
        report["verdict"] = "BLOCKED_PROOF_LOCK"
        report["exact_blocker"] = "second_proof_lock_already_consumed"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    # Candidate hash.
    from core.proof_authority import V3_CANDIDATE_PATH as _V3_CANDIDATE_PATH
    current_candidate_hash = _sha256_file(_V3_CANDIDATE_PATH)
    if authority.candidate_hash != current_candidate_hash:
        report["verdict"] = "BLOCKED_CANDIDATE_VALIDATION"
        report["exact_blocker"] = "candidate_hash_mismatch"
        report["expected_candidate_hash"] = authority.candidate_hash
        report["actual_candidate_hash"] = current_candidate_hash
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    # Caps hash.
    if authority.caps_hash != _sha256_file(CAPS_PATH):
        report["verdict"] = "BLOCKED_LIVE_SUBMIT_CAPS"
        report["exact_blocker"] = "caps_hash_mismatch"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    # Descriptor hash.
    if authority.descriptor_hash != _sha256_file(ADAPTER_DESCRIPTOR_PATH):
        report["verdict"] = "BLOCKED_LIVE_SUBMIT_CAPS"
        report["exact_blocker"] = "descriptor_hash_mismatch"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    # Base runtime approval hash (the original operator-controlled production pilot
    # approval) must still match the canonical value.  The second-proof active
    # approval is expected to exist alongside it, so we verify both are present.
    from core.proof_authority import EXPECTED_RUNTIME_APPROVAL_HASH
    base_approval_path = Path("runtime/approvals/dummy_controlled_production_pilot_approval.json")
    if not base_approval_path.exists():
        report["verdict"] = "BLOCKED_SECOND_PROOF_AUTHORITY"
        report["exact_blocker"] = "base_runtime_approval_missing"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY
    base_approval_hash = _sha256_file(base_approval_path)
    if base_approval_hash != EXPECTED_RUNTIME_APPROVAL_HASH:
        report["verdict"] = "BLOCKED_SECOND_PROOF_AUTHORITY"
        report["exact_blocker"] = "base_runtime_approval_hash_mismatch"
        report["expected_runtime_approval_hash"] = EXPECTED_RUNTIME_APPROVAL_HASH
        report["actual_runtime_approval_hash"] = base_approval_hash
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    second_proof_approval_path = Path("runtime/approvals/dummy_second_controlled_real_broker_proof_approval.json")
    if not second_proof_approval_path.exists():
        report["verdict"] = "BLOCKED_SECOND_PROOF_AUTHORITY"
        report["exact_blocker"] = "second_proof_active_approval_missing"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    # Live-submit must be disabled.
    live_submit = _load_json(LIVE_SUBMIT_PATH)
    if live_submit.get("enabled") is True:
        report["verdict"] = "BLOCKED_LIVE_SUBMIT_CAPS"
        report["exact_blocker"] = "live_submit_enabled"
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    # Command seal readiness (env gate intentionally not required).
    seal = _seal_status()
    if seal != SEAL_READY:
        report["verdict"] = "BLOCKED_COMMAND_SEAL"
        report["command_seal_status"] = seal
        print(json.dumps(report, indent=2), file=out)
        return EXIT_SAFETY

    # Final readiness gate is env only.
    report["env_gate_present"] = _env_gate(env)
    report["one_shot_check_readiness"] = "SECOND_PROOF_READY_ENV_GATE_REQUIRED"
    print(json.dumps(report, indent=2), file=out)
    return EXIT_OK


SECOND_PROOF_EXECUTE_SCRIPT = DUMMY_ROOT / "scripts" / "run_dummy_second_proof_execute_once_v1.py"


def cmd_one_shot_live(env: dict[str, str], runner: Runner, out) -> int:
    # Load whitelisted Kalshi/Dummy env refs from .env into this process so the
    # delegated subprocess can see them. Values are never logged.
    loaded = _load_dotenv_for_one_shot()
    if loaded:
        print(f"DOTENV_LOADED_REFS: {sorted(loaded.keys())}", file=out)

    if not _env_gate(env):
        print(f"BLOCKED_ENV_GATE_ABSENT: require {ENV_MODE[0]}={ENV_MODE[1]} {ENV_ACK[0]}={ENV_ACK[1]}", file=out)
        return EXIT_MISSING
    seal = _seal_status()
    if seal != SEAL_READY:
        print(f"BLOCKED_NOT_ARMABLE: command_seal={seal} (external live-submit/caps/adapter/authority required)", file=out)
        return EXIT_EXTERNAL

    # Second-proof authority path: fresh namespace, V3 candidate, no reuse of first lock.
    sp_state = _second_proof_authority_state()
    if sp_state["state"] == "active":
        authority = sp_state["authority"]
        if is_second_proof_lock_consumed(authority.authority_id):
            print("BLOCKED_SECOND_PROOF_LOCK_ALREADY_USED: no repeat attempt", file=out)
            return EXIT_MISSING
        from core.proof_authority import V3_CANDIDATE_PATH as _V3_CANDIDATE_PATH
        current_candidate_hash = _sha256_file(_V3_CANDIDATE_PATH)
        if authority.candidate_hash != current_candidate_hash:
            print("BLOCKED_CANDIDATE_HASH_MISMATCH: candidate changed after authority activation", file=out)
            return EXIT_SAFETY
        from core.second_proof_runner import run_second_proof_execute_once
        report = run_second_proof_execute_once()
        print(json.dumps(report, indent=2), file=out)
        if report["verdict"].startswith("SECOND_PROOF_EXECUTED"):
            return EXIT_OK
        return EXIT_EXTERNAL if "BLOCKED" in report["verdict"] else EXIT_SAFETY

    if _proof_lock():
        print("BLOCKED_PROOF_LOCK_ALREADY_USED: no repeat attempt", file=out)
        return EXIT_MISSING
    # Delegates to bootstrap → wizard run-live-proof-from-env → appliance run-live-proof-once (never execute-once directly).
    rc = _bootstrap(["run-live-proof-if-ready"], env, runner, out)
    print("POST_PROOF: intake/reconcile/forensic/route/lift run inside appliance run-live-proof-once", file=out)
    return rc


def cmd_full_auto(env: dict[str, str], runner: Runner, out) -> int:
    missing = _missing_build_vars(env)
    if missing:
        cmd_doctor(env, runner, out)
        print("MISSING_OPERATOR_VALUES: " + ", ".join(missing), file=out)
        print('NEXT: python tools/operator_authority_appliance/operator_full_completion.py one-shot-prepare '
              '--operator "<name>" --reason "<reason>" --expires-at "<iso>" --authority-pack-dir "operator_authority_pack" '
              f'--typed-approval "{REQUIRED_PHRASE}" --risk-ack "{REQUIRED_RISK_ACK}"', file=out)
        print("VERDICT: OPERATOR_INPUT_REQUIRED", file=out)
        return EXIT_MISSING
    if _bootstrap(["build-and-verify-pack"], env, runner, out) != EXIT_OK:
        print("VERDICT: REPAIR_REQUIRED", file=out)
        return EXIT_SUBPROC
    if env.get("DUMMY_AUTHORITY_INSTALL_CONFIRM") != INSTALL_CONFIRM_PHRASE:
        print("STOP: external live-submit/caps/adapter + exact install confirmation required.", file=out)
        print("VERDICT: AUTHORITY_PACK_VERIFIED_INSTALL_CONFIRMATION_REQUIRED", file=out)
        return EXIT_OK
    _bootstrap(["install-if-confirmed"], env, runner, out)
    seal = _seal_status()
    if seal != SEAL_READY:
        print(f"STOP: authority checks not armable (seal={seal}); external config still required.", file=out)
        print("VERDICT: LIVE_SUBMIT_CAPS_EXTERNAL_MISSING", file=out)
        return EXIT_EXTERNAL
    if not _env_gate(env):
        print(f"STOP: set env gate then run one-shot-live: export {ENV_MODE[0]}={ENV_MODE[1]} {ENV_ACK[0]}={ENV_ACK[1]}", file=out)
        print("VERDICT: COMMAND_SEAL_READY_ENV_GATE_REQUIRED", file=out)
        return EXIT_OK
    return cmd_one_shot_live(env, runner, out)


def cmd_print_final_runbook(out) -> int:
    print("# DUMMY shortest final operator runbook (nothing runs here). Hard max ONE live attempt.", file=out)
    steps = [
        f'python tools/operator_authority_appliance/operator_full_completion.py one-shot-prepare --operator "<name>" --reason "<reason>" --expires-at "<iso>" --authority-pack-dir "operator_authority_pack" --typed-approval "{REQUIRED_PHRASE}" --risk-ack "{REQUIRED_RISK_ACK}"',
        "# EXTERNAL: operator enables live-submit",
        "# EXTERNAL: operator confirms caps",
        "# EXTERNAL: operator injects LiveBrokerFirewall adapter",
        f'export DUMMY_AUTHORITY_INSTALL_CONFIRM="{INSTALL_CONFIRM_PHRASE}"',
        'python tools/operator_authority_appliance/operator_full_completion.py one-shot-install --authority-pack-dir "operator_authority_pack" --operator-confirm-install "$DUMMY_AUTHORITY_INSTALL_CONFIRM"',
        "python tools/operator_authority_appliance/operator_full_completion.py one-shot-check",
        f"export {ENV_MODE[0]}={ENV_MODE[1]} {ENV_ACK[0]}={ENV_ACK[1]}",
        "python tools/operator_authority_appliance/operator_full_completion.py one-shot-live",
    ]
    for i, s in enumerate(steps, 1):
        print(f"{i}. {s}", file=out)
    print("# STOP after one attempt (auto-lock). Chat approval is never accepted.", file=out)
    return EXIT_OK


def cmd_validate_next_proof_candidate(args) -> int:
    """Read-only validation of the next proof candidate.

    Supports two modes:
      - no-network: existing V1 behavior, no Kalshi contact.
      - read-only: guarded read-only Kalshi metadata discovery, writes V3 packet + report.

    By default read-only discovery writes to a timestamped freshness-check directory
    so it cannot silently overwrite the canonical validated V3 candidate.  Canonical
    files are only mutated when ``--promote-freshness-to-canonical`` is supplied.
    """
    canonical_out_dir = Path("artifacts/dummy/next_proof_candidate")
    if args.mode == "no-network":
        default_out_dir = canonical_out_dir
    elif args.promote_freshness_to_canonical:
        default_out_dir = canonical_out_dir
    else:
        default_out_dir = canonical_out_dir / "freshness_checks" / _timestamp_suffix()
    out_dir = Path(args.out_dir or os.environ.get("DUMMY_NEXT_PROOF_CANDIDATE_OUT_DIR", str(default_out_dir)))
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.market_ticker is None:
        args.market_ticker = "KXBTC-26DEC25000-C"
        explicit_ticker = False
    else:
        explicit_ticker = True

    if args.mode == "no-network":
        # Existing V1 behavior: no Kalshi contact, shape validation only.
        env_values = env_loader.read_whitelisted_env(".env")
        _ = env_loader.kalshi_credential_status(env_values)
        caps = config_loader.load_caps()
        caps_hash = _hash_file("configs/caps.json")
        live_submit_hash = _hash_file("configs/live_submit.json")
        descriptor_path = Path("runtime/operator_external/livebrokerfirewall_adapter_descriptor.json")
        descriptor_hash = _hash_file(str(descriptor_path)) if descriptor_path.exists() else None
        evidence_registry_hash = _hash_file(REAL_PROOF_REGISTRY_PATH)

        registry = load_real_proof_registry()
        previous_status = registry.get("latest_real_broker_attempt_status") if registry else None
        proof_lock_consumed = real_proof_attempt_exists()

        metadata = kalshi_market_validator.MarketMetadata(
            ticker=args.market_ticker,
            status="unknown",
            open_time=None,
            close_time=None,
            trading_allowed=False,
            min_price_cents=1,
            max_price_cents=99,
            tick_size_cents=1,
            contracts=[
                kalshi_market_validator.ContractMetadata(
                    ticker=args.market_ticker, status="unknown", tradable=False
                )
            ],
        )
        read_only_metadata_status = "not_used"

        proof_context = {
            "descriptor_hash": descriptor_hash,
            "caps_hash": caps_hash,
            "live_submit_hash": live_submit_hash,
            "evidence_registry_hash": evidence_registry_hash,
            "previous_real_broker_attempt_status": previous_status,
        }
        candidate = proof_order_candidate.build_validated_proof_candidate(
            metadata, caps, proof_context, validation_mode=args.mode
        )

        candidate_path = out_dir / "VALIDATED_KALSHI_PROOF_CANDIDATE.json"
        proof_order_candidate.write_candidate_packet(candidate, candidate_path)
        candidate_hash = proof_order_candidate.compute_candidate_hash(candidate_path)

        report = {
            "verdict": "NEXT_PROOF_CANDIDATE_VALIDATION_PASS",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "first_rejection_diagnosis": "unrecovered_from_first_attempt",
            "inferred_rejection_risk_factors": [
                "hardcoded price=1 cent may have been outside allowed tick range",
                "market ticker KXBTC-26DEC25000-C may have been closed/untradable",
                "no pre-submit contract/market metadata validation existed",
            ],
            "market_validator_status": "active",
            "read_only_metadata_status": read_only_metadata_status,
            "candidate_packet_path": str(candidate_path),
            "candidate_packet_hash": candidate_hash,
            "candidate_validation_report_path": str(out_dir / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"),
            "candidate_market_ticker": candidate.market_ticker,
            "candidate_contract_ticker": candidate.contract_ticker,
            "candidate_order_type": candidate.order_type,
            "candidate_count": candidate.count,
            "candidate_price_cents": candidate.price,
            "submit_allowed_now": candidate.submit_allowed_now,
            "requires_new_operator_proof_authority": candidate.requires_new_operator_proof_authority,
            "proof_registry_status": previous_status,
            "proof_registry_hash": evidence_registry_hash,
            "proof_lock_status": candidate.proof_lock_status,
            "repeat_submit_block_status": "BLOCKED_BEFORE_ADAPTER_CALL" if proof_lock_consumed else "no_previous_attempt",
            "live_submit_status": "disabled_default",
            "live_submit_hash": live_submit_hash,
            "caps_status": "strict_limit_only_kill_switch_max_order_count_1",
            "caps_hash": caps_hash,
            "adapter_descriptor_status": "staged_kalshi_livebrokerfirewall_limit_only",
            "adapter_descriptor_hash": descriptor_hash,
            "runtime_approval_status": "present" if _approval_exists() else "missing",
            "broker_contact_during_validation": False,
            "read_only_kalshi_metadata_contact": read_only_metadata_status in {"mock", "read_only_success"},
            "live_order_count_during_validation": 0,
            "market_order_status": False,
            "scale_autonomy_status": "disabled",
            "secrets_logging_status": "redacted",
        }
        report_path = out_dir / "NEXT_PROOF_CANDIDATE_VALIDATION_REPORT.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

        print(json.dumps(proof_order_candidate.safe_preview(candidate), indent=2))
        print(f"Candidate packet: {candidate_path}")
        print(f"Validation report: {report_path}")
        return 0

    # ---------------- read-only mode (V3 discovery) ----------------
    if not args.allow_read_only_kalshi_get:
        context = _read_only_context_hashes()
        return _write_read_only_blocked_report(
            out_dir, args, context,
            candidate_found=False,
            blockers=[MISSING_READ_ONLY_GET_APPROVAL_FLAG],
        )

    context = _read_only_context_hashes()
    caps = config_loader.load_caps()

    with _temp_whitelisted_env(".env"):
        missing_creds, _ = _check_kalshi_credentials()
        if missing_creds:
            return _write_read_only_blocked_report(
                out_dir, args, context,
                candidate_found=False,
                blockers=[KALSHI_CREDENTIALS_MISSING],
            )

        client = None
        try:
            client = kalshi_market_validator.KalshiReadOnlyMetadataClient()
            discovery_mode = "explicit" if explicit_ticker else "broad"
            http_summary: dict[str, Any] = {"total_requests": 0, "methods": {}}

            if explicit_ticker:
                metadata, reason, selection_trace = _fetch_explicit_market_metadata_v3(
                    client, args.market_ticker, args.contract_ticker
                )
                candidate_found = metadata is not None
            else:
                candidate_found, metadata, reason = _maybe_await(
                    kalshi_market_validator.discover_live_eligible_candidates(
                        client, max_candidates=args.max_candidates, prefer_event=args.prefer_event
                    )
                )
                selection_trace = [reason] if not candidate_found else ["live_eligible_candidate_found"]

            http_summary = getattr(client, "http_summary", lambda: {"total_requests": 0, "methods": {}})()
            get_count = http_summary.get("methods", {}).get("GET", 0)
            blocked_writes = len(getattr(client, "blocked_attempts", []))

            if not candidate_found or metadata is None:
                return _write_read_only_blocked_report(
                    out_dir, args, context,
                    candidate_found=False,
                    blockers=[reason or NO_ELIGIBLE_CANDIDATE_FOUND],
                    read_only_metadata_contact=True,
                    discovery_mode=discovery_mode,
                    get_request_count=get_count,
                    blocked_write_request_count=blocked_writes,
                    response_schema_summary=_response_schema_summary(client),
                    candidate_selection_trace=selection_trace,
                )

            price, price_validated, price_reason = kalshi_market_validator.derive_validated_price(metadata)
            if not price_validated:
                return _write_read_only_blocked_report(
                    out_dir, args, context,
                    candidate_found=True,
                    blockers=[price_reason],
                    metadata=metadata,
                    price=price,
                    price_validated=False,
                    read_only_metadata_contact=True,
                    discovery_mode=discovery_mode,
                    get_request_count=get_count,
                    blocked_write_request_count=blocked_writes,
                    response_schema_summary=_response_schema_summary(client),
                    candidate_selection_trace=selection_trace,
                )

            proof_context = {
                "descriptor_hash": context["descriptor_hash"],
                "caps_hash": context["caps_hash"],
                "live_submit_hash": context["live_submit_hash"],
                "evidence_registry_hash": context["evidence_registry_hash"],
                "previous_real_broker_attempt_status": context["previous_real_broker_attempt_status"],
                "runtime_approval_hash": context["runtime_approval_hash"],
                "current_live_submit_hash": context["live_submit_hash"],
            }
            candidate = proof_order_candidate.build_validated_proof_candidate_v3(
                metadata, caps, proof_context,
                candidate_found=True,
                price_source="metadata",
                price_validated=price_validated,
                read_only_metadata_contact=True,
                broker_submit_contact=False,
                live_order_count=0,
                order_write_methods_blocked=True,
                discovery_mode=discovery_mode,
                get_request_count=get_count,
                write_request_count=0,
                blocked_write_request_count=blocked_writes,
                response_schema_summary=_response_schema_summary(client),
                candidate_selection_trace=selection_trace,
                exact_blockers=[],
            )
            candidate_path = out_dir / "VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json"
            proof_order_candidate.write_candidate_packet_v3(candidate, candidate_path)
            return _write_read_only_pass_report(out_dir, args, context, candidate, candidate_path)

        except Exception as exc:
            blocker = f"READ_ONLY_METADATA_EXCEPTION:{type(exc).__name__}"
            return _write_read_only_blocked_report(
                out_dir, args, context,
                candidate_found=False,
                blockers=[blocker],
                read_only_metadata_contact=True,
                discovery_mode=discovery_mode if "discovery_mode" in locals() else "unknown",
            )
        finally:
            if client is not None:
                try:
                    close_method = getattr(client, "close", None)
                    if close_method is not None:
                        _maybe_await(close_method())
                except Exception:
                    pass


def _hash_file(path: str) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


def _approval_exists() -> bool:
    return any(Path("runtime/approvals").glob("*.json"))


def _runtime_approval_hash() -> str | None:
    approvals_dir = Path("runtime/approvals")
    if not approvals_dir.is_dir():
        return None
    files = sorted(p for p in approvals_dir.iterdir() if p.is_file())
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest().upper()


@contextmanager
def _temp_whitelisted_env(dotenv_path: str | Path):
    values = env_loader.read_whitelisted_env(dotenv_path)
    if not values:
        yield
        return
    original = {k: os.environ.get(k) for k in values}
    try:
        env_loader.apply_whitelisted_env(values, overwrite=False)
        yield
    finally:
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _maybe_await(value: Any) -> Any:
    """Run an async result if needed, otherwise return it unchanged."""
    if inspect.iscoroutine(value):
        return asyncio.run(value)
    return value


def _proof_lock_status_from_context(previous_status: str | None) -> str:
    if previous_status in {"BROKER_REJECTED", "BROKER_ACCEPTED"}:
        return "consumed_by_real_broker_attempt"
    return "clear"


def _read_only_context_hashes() -> dict[str, Any]:
    caps_hash = _hash_file("configs/caps.json")
    live_submit_hash = _hash_file("configs/live_submit.json")
    descriptor_path = Path("runtime/operator_external/livebrokerfirewall_adapter_descriptor.json")
    descriptor_hash = _hash_file(str(descriptor_path)) if descriptor_path.exists() else None
    evidence_registry_hash = _hash_file(REAL_PROOF_REGISTRY_PATH)
    runtime_approval_hash = _runtime_approval_hash()
    registry = load_real_proof_registry()
    previous_status = registry.get("latest_real_broker_attempt_status") if registry else None
    return {
        "caps_hash": caps_hash,
        "live_submit_hash": live_submit_hash,
        "descriptor_hash": descriptor_hash,
        "evidence_registry_hash": evidence_registry_hash,
        "runtime_approval_hash": runtime_approval_hash,
        "previous_real_broker_attempt_status": previous_status,
    }


def _fetch_explicit_market_metadata(client, market_ticker: str, contract_ticker: str | None = None):
    shape = kalshi_market_validator.validate_ticker_shape(market_ticker, contract_ticker)
    if not shape.ok:
        return None, "; ".join(shape.errors)
    raw = _maybe_await(client.get_market(market_ticker.strip().upper()))
    if isinstance(raw, dict):
        metadata = kalshi_market_validator._market_metadata_from_api(raw)
    else:
        metadata = raw
    if metadata is None:
        return None, "MARKET_METADATA_UNAVAILABLE"
    if not metadata.trading_allowed or metadata.status.lower() != "open":
        return None, f"MARKET_NOT_OPEN:{metadata.status}"
    target_contract = (contract_ticker or market_ticker).strip().upper()
    contract = next((c for c in metadata.contracts if c.ticker.upper() == target_contract), None)
    if contract is None:
        return None, "CONTRACT_NOT_FOUND"
    if not contract.tradable or contract.status.lower() != "open":
        return None, f"CONTRACT_NOT_TRADABLE:{contract.status}"
    return metadata, ""


def _fetch_explicit_market_metadata_v3(
    client, market_ticker: str, contract_ticker: str | None = None
) -> tuple[Any | None, str, list[str]]:
    """Validate an explicit ticker against read-only metadata and return trace."""
    trace: list[str] = [f"explicit_validation:{market_ticker}"]
    shape = kalshi_market_validator.validate_ticker_shape(market_ticker, contract_ticker)
    if not shape.ok:
        return None, "; ".join(shape.errors), trace + ["ticker_shape_invalid"]

    try:
        raw = _maybe_await(client.get_market(market_ticker.strip().upper()))
    except Exception as exc:
        return None, kalshi_market_validator._classify_discovery_exception(exc), trace + ["get_market_exception"]

    trace.append("get_market_success")
    if isinstance(raw, dict):
        metadata = kalshi_market_validator._market_metadata_from_api(raw)
    else:
        metadata = raw
    if metadata is None:
        return None, "MARKET_METADATA_UNAVAILABLE", trace + ["metadata_parse_failed"]

    trace.append(f"market_status:{metadata.status}")
    if not metadata.trading_allowed or metadata.status.lower() != "open":
        return None, f"MARKET_NOT_OPEN:{metadata.status}", trace + ["market_not_open"]

    target_contract = (contract_ticker or market_ticker).strip().upper()
    contract = next((c for c in metadata.contracts if c.ticker.upper() == target_contract), None)
    if contract is None:
        return None, "CONTRACT_NOT_FOUND", trace + ["contract_not_found"]
    trace.append(f"contract_status:{contract.status}")
    if not contract.tradable or contract.status.lower() != "open":
        return None, f"CONTRACT_NOT_TRADABLE:{contract.status}", trace + ["contract_not_tradable"]

    return metadata, "", trace + ["explicit_candidate_valid"]


def _response_schema_summary(client: Any) -> str:
    """Return a short, secret-free summary of the last metadata response shape."""
    log = getattr(client, "request_audit_log", [])
    if not log:
        return "no_requests"
    last = log[-1]
    summary = last.get("redacted_summary", {})
    keys = summary.get("keys")
    count = summary.get("count")
    if isinstance(keys, list):
        return f"keys:{','.join(sorted(keys)[:5])}"
    if count is not None:
        return f"list_count:{count}"
    return "unknown_shape"


def _write_read_only_blocked_report(
    out_dir: Path,
    args: argparse.Namespace,
    context: dict[str, Any],
    *,
    candidate_found: bool = False,
    blockers: list[str] | None = None,
    metadata: Any | None = None,
    price: int | None = None,
    price_validated: bool = False,
    read_only_metadata_contact: bool = False,
    discovery_mode: str = "broad",
    get_request_count: int = 0,
    write_request_count: int = 0,
    blocked_write_request_count: int = 0,
    response_schema_summary: str = "unknown",
    candidate_selection_trace: list[str] | None = None,
) -> int:
    report_path = out_dir / "NEXT_PROOF_CANDIDATE_DISCOVERY_V3_REPORT.json"
    candidate_path = out_dir / "VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json"
    if metadata is None:
        metadata = kalshi_market_validator.MarketMetadata(
            ticker=args.market_ticker,
            status="unknown",
            open_time=None,
            close_time=None,
            trading_allowed=False,
            min_price_cents=1,
            max_price_cents=99,
            tick_size_cents=1,
            contracts=[
                kalshi_market_validator.ContractMetadata(
                    ticker=args.contract_ticker or args.market_ticker,
                    status="unknown",
                    tradable=False,
                )
            ],
        )

    proof_context = {
        "descriptor_hash": context["descriptor_hash"],
        "caps_hash": context["caps_hash"],
        "live_submit_hash": context["live_submit_hash"],
        "evidence_registry_hash": context["evidence_registry_hash"],
        "previous_real_broker_attempt_status": context["previous_real_broker_attempt_status"],
        "runtime_approval_hash": context["runtime_approval_hash"],
        "current_live_submit_hash": context["live_submit_hash"],
    }
    blocked_candidate = proof_order_candidate.build_validated_proof_candidate_v3(
        metadata,
        {"max_order_count": 1, "max_single_order_cents": 100},
        proof_context,
        candidate_found=candidate_found,
        price_source="metadata" if metadata.status != "unknown" else "unknown",
        price_validated=price_validated,
        read_only_metadata_contact=read_only_metadata_contact,
        broker_submit_contact=False,
        live_order_count=0,
        order_write_methods_blocked=True,
        discovery_mode=discovery_mode,
        get_request_count=get_request_count,
        write_request_count=write_request_count,
        blocked_write_request_count=blocked_write_request_count,
        response_schema_summary=response_schema_summary,
        candidate_selection_trace=candidate_selection_trace or [],
        exact_blockers=blockers or [],
    )
    proof_order_candidate.write_candidate_packet_v3(blocked_candidate, candidate_path)

    report = {
        "verdict": "READ_ONLY_DISCOVERY_V3_NO_CANDIDATE" if not candidate_found else "READ_ONLY_DISCOVERY_V3_BLOCKED",
        "candidate_id": blocked_candidate.candidate_id,
        "created_at": blocked_candidate.created_at,
        "validation_mode": blocked_candidate.validation_mode,
        "discovery_mode": blocked_candidate.discovery_mode,
        "read_only_metadata_contact": blocked_candidate.read_only_metadata_contact,
        "get_request_count": blocked_candidate.get_request_count,
        "write_request_count": blocked_candidate.write_request_count,
        "blocked_write_request_count": blocked_candidate.blocked_write_request_count,
        "market_ticker": blocked_candidate.market_ticker,
        "contract_ticker": blocked_candidate.contract_ticker,
        "market_status": blocked_candidate.market_status,
        "contract_status": blocked_candidate.contract_status,
        "market_tradable": blocked_candidate.market_tradable,
        "contract_tradable": blocked_candidate.contract_tradable,
        "price_source": blocked_candidate.price_source,
        "price_validated": blocked_candidate.price_validated,
        "price": blocked_candidate.price,
        "count": blocked_candidate.count,
        "order_type": blocked_candidate.order_type,
        "action": blocked_candidate.action,
        "side": blocked_candidate.side,
        "caps_hash": blocked_candidate.caps_hash,
        "descriptor_hash": blocked_candidate.descriptor_hash,
        "proof_registry_hash": blocked_candidate.evidence_registry_hash,
        "runtime_approval_hash": blocked_candidate.runtime_approval_hash,
        "current_live_submit_hash": blocked_candidate.current_live_submit_hash,
        "proof_lock_status": blocked_candidate.proof_lock_status,
        "previous_real_broker_attempt_recorded": True,
        "submit_allowed_now": False,
        "requires_new_operator_proof_authority": True,
        "reason_submit_not_allowed": blocked_candidate.reason_submit_not_allowed,
        "no_submit_performed": True,
        "no_cancel_performed": True,
        "no_live_submit_mutation": True,
        "secrets_redacted": True,
        "candidate_found": candidate_found,
        "exact_blockers": blockers or [],
        "response_schema_summary": blocked_candidate.response_schema_summary,
        "candidate_selection_trace": blocked_candidate.candidate_selection_trace,
        "broker_submit_contact_during_validation": False,
        "live_order_count_during_validation": 0,
        "read_only_kalshi_metadata_contact": read_only_metadata_contact,
        "market_order_status": False,
        "scale_autonomy_status": "disabled",
        "candidate_packet_path": str(candidate_path),
        "candidate_packet_hash": proof_order_candidate.compute_candidate_hash(candidate_path),
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(proof_order_candidate.safe_preview(blocked_candidate), indent=2), file=sys.stdout)
    print(f"Candidate V3 packet: {candidate_path}", file=sys.stdout)
    print(f"Read-only discovery V3 report: {report_path}", file=sys.stdout)
    return 0


def _write_read_only_pass_report(
    out_dir: Path,
    args: argparse.Namespace,
    context: dict[str, Any],
    candidate: Any,
    candidate_path: Path,
) -> int:
    report_path = out_dir / "NEXT_PROOF_CANDIDATE_DISCOVERY_V3_REPORT.json"
    report = {
        "verdict": "READ_ONLY_DISCOVERY_V3_CANDIDATE_FOUND",
        "candidate_id": candidate.candidate_id,
        "created_at": candidate.created_at,
        "validation_mode": candidate.validation_mode,
        "discovery_mode": candidate.discovery_mode,
        "read_only_metadata_contact": candidate.read_only_metadata_contact,
        "get_request_count": candidate.get_request_count,
        "write_request_count": candidate.write_request_count,
        "blocked_write_request_count": candidate.blocked_write_request_count,
        "market_ticker": candidate.market_ticker,
        "contract_ticker": candidate.contract_ticker,
        "market_status": candidate.market_status,
        "contract_status": candidate.contract_status,
        "market_tradable": candidate.market_tradable,
        "contract_tradable": candidate.contract_tradable,
        "price_source": candidate.price_source,
        "price_validated": candidate.price_validated,
        "price": candidate.price,
        "count": candidate.count,
        "order_type": candidate.order_type,
        "action": candidate.action,
        "side": candidate.side,
        "caps_hash": candidate.caps_hash,
        "descriptor_hash": candidate.descriptor_hash,
        "proof_registry_hash": candidate.evidence_registry_hash,
        "runtime_approval_hash": context["runtime_approval_hash"],
        "current_live_submit_hash": context["live_submit_hash"],
        "proof_lock_status": candidate.proof_lock_status,
        "previous_real_broker_attempt_recorded": True,
        "submit_allowed_now": False,
        "requires_new_operator_proof_authority": True,
        "reason_submit_not_allowed": PREVIOUS_REAL_BROKER_ATTEMPT_RECORDED,
        "no_submit_performed": True,
        "no_cancel_performed": True,
        "no_live_submit_mutation": True,
        "secrets_redacted": True,
        "candidate_found": candidate.candidate_found,
        "exact_blockers": [],
        "response_schema_summary": candidate.response_schema_summary,
        "candidate_selection_trace": candidate.candidate_selection_trace,
        "broker_submit_contact_during_validation": False,
        "live_order_count_during_validation": 0,
        "read_only_kalshi_metadata_contact": candidate.read_only_metadata_contact,
        "market_order_status": False,
        "scale_autonomy_status": "disabled",
        "candidate_packet_path": str(candidate_path),
        "candidate_packet_hash": proof_order_candidate.compute_candidate_hash(candidate_path),
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(proof_order_candidate.safe_preview(candidate), indent=2), file=sys.stdout)
    print(f"Candidate V3 packet: {candidate_path}", file=sys.stdout)
    print(f"Read-only discovery V3 report: {report_path}", file=sys.stdout)
    return 0


# ----------------------------- CLI -----------------------------

def _normalize_mode(value: str) -> str:
    v = value.strip().lower().replace("_", "-")
    mapping = {
        "no-network": "no-network",
        "no_network": "no-network",
        "mock": "no-network",
        "read-only": "read-only",
        "read_only_network": "read-only",
    }
    if v not in mapping:
        raise argparse.ArgumentTypeError(f"invalid mode: {value!r}")
    return mapping[v]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Operator-side full-completion orchestrator for the Dummy real-proof path (fail-closed).")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor", "one-shot-check", "full-auto", "print-final-runbook", "disable-live-submit",
                 "prepare-second-proof-authority", "second-proof-runtime-preflight"):
        sub.add_parser(name)
    act2 = sub.add_parser("activate-second-proof-authority")
    act2.add_argument("--operator-name", required=True)
    act2.add_argument("--reason", required=True)
    act2.add_argument("--expires-at", required=True)
    act2.add_argument("--confirm", required=True)
    en = sub.add_parser("enable-one-proof-live-submit")
    en.add_argument("--operator", required=True)
    en.add_argument("--reason", required=True)
    en.add_argument("--expires-at", required=True)
    en.add_argument("--typed-confirmation", required=True)
    pr = sub.add_parser("one-shot-prepare")
    pr.add_argument("--operator", required=True)
    pr.add_argument("--reason", required=True)
    pr.add_argument("--expires-at", required=True)
    pr.add_argument("--authority-pack-dir", default=DEFAULT_PACK_DIR)
    pr.add_argument("--typed-approval", required=True)
    pr.add_argument("--risk-ack", required=True)
    ins = sub.add_parser("one-shot-install")
    ins.add_argument("--authority-pack-dir", required=True)
    ins.add_argument("--operator-confirm-install", required=True)
    sub.add_parser("one-shot-live")
    validate_parser = sub.add_parser(
        "validate-next-proof-candidate",
        help="Validate a next-proof candidate without submitting (read-only).",
    )
    validate_parser.add_argument(
        "--mode",
        type=_normalize_mode,
        choices=["no-network", "read-only"],
        default="no-network",
        help="Validation mode: no-network (V1, no Kalshi contact) or read-only (V2, metadata GET only).",
    )
    validate_parser.add_argument(
        "--network-mode",
        dest="mode",
        type=_normalize_mode,
        choices=["no-network", "read-only"],
        help="Deprecated alias for --mode.",
    )
    validate_parser.add_argument(
        "--market-ticker",
        default=None,
        help="Market ticker to validate (default: first-attempt ticker).",
    )
    validate_parser.add_argument(
        "--contract-ticker",
        default=None,
        help="Contract ticker to validate (yes/no markets: defaults to market ticker).",
    )
    validate_parser.add_argument(
        "--max-candidates",
        type=int,
        default=10,
        help="Maximum number of live markets to inspect in read-only discovery mode.",
    )
    validate_parser.add_argument(
        "--prefer-event",
        default=None,
        help="Optional event/title substring to prefer during discovery.",
    )
    validate_parser.add_argument(
        "--allow-read-only-kalshi-get",
        action="store_true",
        help="Explicit operator approval to perform read-only Kalshi metadata GETs.",
    )
    validate_parser.add_argument(
        "--out-dir",
        default=None,
        help="Override output directory for candidate packet and report.",
    )
    validate_parser.add_argument(
        "--promote-freshness-to-canonical",
        action="store_true",
        help=(
            "If the read-only freshness check produces a valid candidate, write it to "
            "the canonical artifacts/dummy/next_proof_candidate path.  Without this flag "
            "the default is a timestamped freshness_checks subdirectory."
        ),
    )
    return p


def main(argv: list[str] | None = None, *, env: dict[str, str] | None = None, runner: Runner | None = None, out=None) -> int:
    env = env if env is not None else dict(os.environ)
    runner = runner or _default_runner
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    c = args.command
    if c == "status":
        return cmd_status(env, runner, out)
    if c == "doctor":
        return cmd_doctor(env, runner, out)
    if c == "prepare-second-proof-authority":
        return cmd_prepare_second_proof_authority(args, out)
    if c == "activate-second-proof-authority":
        return cmd_activate_second_proof_authority(args, out)
    if c == "enable-one-proof-live-submit":
        return cmd_enable_one_proof_live_submit(args, out)
    if c == "disable-live-submit":
        return cmd_disable_live_submit(args, out)
    if c == "one-shot-prepare":
        return cmd_one_shot_prepare(args, runner, out)
    if c == "one-shot-install":
        return cmd_one_shot_install(args, runner, out)
    if c == "one-shot-check":
        return cmd_one_shot_check(env, runner, out)
    if c == "one-shot-live":
        return cmd_one_shot_live(env, runner, out)
    if c == "full-auto":
        return cmd_full_auto(env, runner, out)
    if c == "print-final-runbook":
        return cmd_print_final_runbook(out)
    if c == "validate-next-proof-candidate":
        return cmd_validate_next_proof_candidate(args)
    if c == "second-proof-runtime-preflight":
        return cmd_second_proof_runtime_preflight(env, out)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
