"""Operator-side env provisioning helper for the DUMMY Operator Authority Appliance.

Removes the clerical block (setting six operator variables) WITHOUT ever letting Dummy self-authorize.
This wizard only: reports env status, prints shell-safe export/command templates, writes operator-owned
.env files, and shells out to the EXISTING appliance CLI for build/verify/install/checks/live-proof. It
never creates runtime/approvals itself, never modifies live-submit/caps, never injects a broker adapter,
never calls the Dummy execute-once script directly, and never runs live-proof without the exact env gate.
It adds no Dummy stage/gate/dashboard and no V305+ architecture.

Exit codes: 0 success · 2 missing/mismatched operator input · 3 subprocess failure · 4 safety rejection.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

APPLIANCE_DIR = Path(__file__).resolve().parent
APPLIANCE_CLI = APPLIANCE_DIR / "operator_authority_appliance.py"

# Reuse the appliance's canonical constants/validators (single source of truth; no duplication of logic).
_spec = importlib.util.spec_from_file_location("operator_authority_appliance", APPLIANCE_CLI)
_app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_app)

REQUIRED_PHRASE = _app.REQUIRED_PHRASE
REQUIRED_RISK_ACK = _app.REQUIRED_ACKNOWLEDGE_RISK
INSTALL_CONFIRM_PHRASE = _app.INSTALL_CONFIRM_PHRASE
ENV_MODE = _app.ENV_MODE
ENV_ACK = _app.ENV_ACK
BROAD_TERMS = _app.BROAD_TERMS
MARKET_ALLOW_TERMS = _app.MARKET_ALLOW_TERMS
SCALE_AUTONOMY_TERMS = _app.SCALE_AUTONOMY_TERMS
REQUIRED_PROOF_TARGET = _app.REQUIRED_PROOF_TARGET
CONFIRM_LIVE_PROOF_ENV_GATE = "I understand this arms the env gate but Dummy still requires all authority checks before one live proof"
DEFAULT_PACK_DIR = "operator_authority_pack"

BUILD_VARS = ["DUMMY_OPERATOR_NAME", "DUMMY_OPERATOR_REASON", "DUMMY_OPERATOR_EXPIRES_AT", "DUMMY_AUTHORITY_PACK_DIR", "DUMMY_TYPED_APPROVAL", "DUMMY_RISK_ACK"]
ALL_VARS = BUILD_VARS + ["DUMMY_AUTHORITY_INSTALL_CONFIRM", "DUMMY_LIVE_PROOF_MODE", "DUMMY_LIVE_PROOF_ACK"]

EXIT_OK, EXIT_MISSING, EXIT_SUBPROC, EXIT_SAFETY = 0, 2, 3, 4

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


def _default_runner(cmd: list[str]) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(cmd, cwd=str(APPLIANCE_DIR.parents[1]), capture_output=True, text=True)  # shell=False


def _contains(text: str, terms: list[str]) -> bool:
    low = (text or "").lower()
    return any(t in low for t in terms)


def _appliance_cmd(*args: str) -> list[str]:
    return [sys.executable, str(APPLIANCE_CLI), *args]


def _safety_reject_approval(typed_approval: str, risk_ack: str, reason: str) -> list[str]:
    errs: list[str] = []
    if typed_approval != REQUIRED_PHRASE:
        errs.append("APPROVAL_PHRASE_NOT_EXACT")
    if risk_ack != REQUIRED_RISK_ACK:
        errs.append("RISK_ACK_NOT_EXACT")
    combined = f"{reason} {risk_ack} {typed_approval}"
    if _contains(combined, BROAD_TERMS):
        errs.append("BROAD_APPROVAL_REJECTED")
    if _contains(f"{reason} {risk_ack}", MARKET_ALLOW_TERMS):
        errs.append("MARKET_ORDER_APPROVAL_REJECTED")
    if _contains(f"{reason} {risk_ack}", SCALE_AUTONOMY_TERMS):
        errs.append("SCALE_OR_AUTONOMY_APPROVAL_REJECTED")
    return errs


# ----------------------------- commands -----------------------------

def cmd_status(env: dict[str, str], out) -> int:
    print("# DUMMY operator env status (read-only, no writes)", file=out)
    for var in ALL_VARS:
        print(f"{var}={'SET' if env.get(var) else 'UNSET'}", file=out)
    if env.get("DUMMY_TYPED_APPROVAL"):
        print(f"typed_approval_exact={env['DUMMY_TYPED_APPROVAL'] == REQUIRED_PHRASE}", file=out)
    if env.get("DUMMY_RISK_ACK"):
        print(f"risk_ack_exact={env['DUMMY_RISK_ACK'] == REQUIRED_RISK_ACK}", file=out)
    if env.get("DUMMY_AUTHORITY_INSTALL_CONFIRM"):
        print(f"install_confirm_exact={env['DUMMY_AUTHORITY_INSTALL_CONFIRM'] == INSTALL_CONFIRM_PHRASE}", file=out)
    gate = env.get(ENV_MODE[0]) == ENV_MODE[1] and env.get(ENV_ACK[0]) == ENV_ACK[1]
    print(f"env_gate_present={gate}", file=out)
    return EXIT_OK


def cmd_print_export_template(out) -> int:
    print("# Operator env export template (fill placeholders, then `source` it). Nothing runs here.", file=out)
    print('export DUMMY_OPERATOR_NAME="<operator>"', file=out)
    print('export DUMMY_OPERATOR_REASON="<reason>"', file=out)
    print('export DUMMY_OPERATOR_EXPIRES_AT="<iso-timestamp>"', file=out)
    print(f'export DUMMY_AUTHORITY_PACK_DIR="{DEFAULT_PACK_DIR}"', file=out)
    print(f'export DUMMY_TYPED_APPROVAL={shlex.quote(REQUIRED_PHRASE)}', file=out)
    print(f'export DUMMY_RISK_ACK={shlex.quote(REQUIRED_RISK_ACK)}', file=out)
    print(f'# export DUMMY_AUTHORITY_INSTALL_CONFIRM={shlex.quote(INSTALL_CONFIRM_PHRASE)}', file=out)
    print(f'# export {ENV_MODE[0]}={ENV_MODE[1]}', file=out)
    print(f'# export {ENV_ACK[0]}={ENV_ACK[1]}', file=out)
    return EXIT_OK


def cmd_write_env_file(args, out) -> int:
    if not args.operator or not args.reason or not args.expires_at:
        print("MISSING: --operator / --reason / --expires-at required", file=out)
        return EXIT_MISSING
    errs = _safety_reject_approval(args.typed_approval, args.risk_ack, args.reason)
    if errs:
        print("SAFETY_REJECTED: " + ", ".join(errs), file=out)
        return EXIT_SAFETY
    if args.include_live_proof_env_gate and args.confirm_live_proof_env_gate != CONFIRM_LIVE_PROOF_ENV_GATE:
        print("SAFETY_REJECTED: LIVE_PROOF_ENV_GATE_CONFIRMATION_NOT_EXACT", file=out)
        return EXIT_SAFETY
    pack_dir = args.authority_pack_dir or DEFAULT_PACK_DIR
    lines = [
        "# Operator-owned env file. NOT an approval. NOT installed until install-authority-pack is run.",
        f"DUMMY_OPERATOR_NAME={shlex.quote(args.operator)}",
        f"DUMMY_OPERATOR_REASON={shlex.quote(args.reason)}",
        f"DUMMY_OPERATOR_EXPIRES_AT={shlex.quote(args.expires_at)}",
        f"DUMMY_AUTHORITY_PACK_DIR={shlex.quote(pack_dir)}",
        f"DUMMY_TYPED_APPROVAL={shlex.quote(REQUIRED_PHRASE)}",
        f"DUMMY_RISK_ACK={shlex.quote(REQUIRED_RISK_ACK)}",
    ]
    if args.include_install_confirmation:
        lines.append(f"DUMMY_AUTHORITY_INSTALL_CONFIRM={shlex.quote(INSTALL_CONFIRM_PHRASE)}")
    else:
        lines.append(f"# DUMMY_AUTHORITY_INSTALL_CONFIRM={shlex.quote(INSTALL_CONFIRM_PHRASE)}")
    if args.include_live_proof_env_gate:
        lines.append(f"{ENV_MODE[0]}={ENV_MODE[1]}")
        lines.append(f"{ENV_ACK[0]}={ENV_ACK[1]}")
    else:
        lines.append(f"# {ENV_MODE[0]}={ENV_MODE[1]}")
        lines.append(f"# {ENV_ACK[0]}={ENV_ACK[1]}")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE_ENV_FILE: {args.output}", file=out)
    return EXIT_OK


def _missing_build_vars(env: dict[str, str]) -> list[str]:
    return [v for v in BUILD_VARS if not env.get(v)]


def cmd_print_build_command(env: dict[str, str], out) -> int:
    missing = _missing_build_vars(env)
    if missing:
        print("MISSING_VARS: " + ", ".join(missing), file=out)
        return EXIT_MISSING
    cmd = _appliance_cmd("build-authority-pack", "--output", env["DUMMY_AUTHORITY_PACK_DIR"],
                         "--operator", env["DUMMY_OPERATOR_NAME"], "--reason", env["DUMMY_OPERATOR_REASON"],
                         "--expires-at", env["DUMMY_OPERATOR_EXPIRES_AT"], "--proof-target", REQUIRED_PROOF_TARGET,
                         "--typed-approval", env["DUMMY_TYPED_APPROVAL"], "--acknowledge-risk", env["DUMMY_RISK_ACK"])
    print(" ".join(shlex.quote(c) for c in cmd), file=out)
    return EXIT_OK


def cmd_print_full_operator_sequence(out) -> int:
    steps = [
        "source <operator-env-file>",
        "python tools/operator_authority_appliance/operator_env_wizard.py build-pack-from-env",
        "python tools/operator_authority_appliance/operator_env_wizard.py verify-pack-from-env",
        "# STOP: operator manually enables live-submit externally (Dummy must NOT do this)",
        "# STOP: operator manually confirms caps externally + injects LiveBrokerFirewall adapter externally",
        "python tools/operator_authority_appliance/operator_env_wizard.py install-pack-from-env  # needs exact DUMMY_AUTHORITY_INSTALL_CONFIRM",
        "python tools/operator_authority_appliance/operator_env_wizard.py run-checks-from-env",
        f"# STOP: set env gate {ENV_MODE[0]}={ENV_MODE[1]} {ENV_ACK[0]}={ENV_ACK[1]} only when armable",
        "python tools/operator_authority_appliance/operator_env_wizard.py run-live-proof-from-env  # ONE attempt, auto-lock",
        "# post-proof intake/reconcile/forensic/route run automatically inside run-live-proof-once",
    ]
    print("# DUMMY safe operator sequence (nothing runs here). Hard max ONE live attempt.", file=out)
    for i, s in enumerate(steps, 1):
        print(f"{i}. {s}", file=out)
    return EXIT_OK


def _shell_out(cmd: list[str], runner: Runner, out) -> int:
    proc = runner(cmd)
    if proc.stdout:
        print(proc.stdout.rstrip(), file=out)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr.rstrip()[:500], file=out)
        return EXIT_SUBPROC
    return EXIT_OK


def cmd_build_pack_from_env(env: dict[str, str], runner: Runner, out) -> int:
    missing = _missing_build_vars(env)
    if missing:
        print("MISSING_VARS: " + ", ".join(missing), file=out)
        return EXIT_MISSING
    errs = _safety_reject_approval(env["DUMMY_TYPED_APPROVAL"], env["DUMMY_RISK_ACK"], env["DUMMY_OPERATOR_REASON"])
    if errs:
        print("SAFETY_REJECTED: " + ", ".join(errs), file=out)
        return EXIT_SAFETY
    cmd = _appliance_cmd("build-authority-pack", "--output", env["DUMMY_AUTHORITY_PACK_DIR"],
                         "--operator", env["DUMMY_OPERATOR_NAME"], "--reason", env["DUMMY_OPERATOR_REASON"],
                         "--expires-at", env["DUMMY_OPERATOR_EXPIRES_AT"], "--proof-target", REQUIRED_PROOF_TARGET,
                         "--typed-approval", env["DUMMY_TYPED_APPROVAL"], "--acknowledge-risk", env["DUMMY_RISK_ACK"])
    return _shell_out(cmd, runner, out)


def cmd_verify_pack_from_env(env: dict[str, str], runner: Runner, out) -> int:
    if not env.get("DUMMY_AUTHORITY_PACK_DIR"):
        print("MISSING_VARS: DUMMY_AUTHORITY_PACK_DIR", file=out)
        return EXIT_MISSING
    return _shell_out(_appliance_cmd("verify-authority-pack", "--source", env["DUMMY_AUTHORITY_PACK_DIR"]), runner, out)


def cmd_install_pack_from_env(env: dict[str, str], runner: Runner, out) -> int:
    if not env.get("DUMMY_AUTHORITY_PACK_DIR"):
        print("MISSING_VARS: DUMMY_AUTHORITY_PACK_DIR", file=out)
        return EXIT_MISSING
    if env.get("DUMMY_AUTHORITY_INSTALL_CONFIRM") != INSTALL_CONFIRM_PHRASE:
        print("INSTALL_CONFIRMATION_REQUIRED (exact): " + INSTALL_CONFIRM_PHRASE, file=out)
        return EXIT_MISSING
    cmd = _appliance_cmd("install-authority-pack", "--source", env["DUMMY_AUTHORITY_PACK_DIR"],
                         "--operator-confirm-install", env["DUMMY_AUTHORITY_INSTALL_CONFIRM"])
    return _shell_out(cmd, runner, out)


def cmd_run_checks_from_env(runner: Runner, out) -> int:
    return _shell_out(_appliance_cmd("run-authority-checks"), runner, out)


def cmd_run_live_proof_from_env(env: dict[str, str], runner: Runner, out) -> int:
    if env.get(ENV_MODE[0]) != ENV_MODE[1] or env.get(ENV_ACK[0]) != ENV_ACK[1]:
        print(f"BLOCKED_ENV_GATE_ABSENT: require {ENV_MODE[0]}={ENV_MODE[1]} {ENV_ACK[0]}={ENV_ACK[1]}", file=out)
        return EXIT_MISSING
    return _shell_out(_appliance_cmd("run-live-proof-once"), runner, out)


# ----------------------------- CLI -----------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Operator-side env wizard for the Dummy authority appliance (fail-closed).")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("status", "print-export-template", "print-build-command", "print-full-operator-sequence",
                 "build-pack-from-env", "verify-pack-from-env", "install-pack-from-env", "run-checks-from-env",
                 "run-live-proof-from-env"):
        sub.add_parser(name)
    w = sub.add_parser("write-env-file")
    w.add_argument("--output", required=True)
    w.add_argument("--operator", required=True)
    w.add_argument("--reason", required=True)
    w.add_argument("--expires-at", required=True)
    w.add_argument("--authority-pack-dir", default=DEFAULT_PACK_DIR)
    w.add_argument("--typed-approval", required=True)
    w.add_argument("--risk-ack", required=True)
    w.add_argument("--include-install-confirmation", action="store_true")
    w.add_argument("--include-live-proof-env-gate", action="store_true")
    w.add_argument("--confirm-live-proof-env-gate", default="")
    return p


def main(argv: list[str] | None = None, *, env: dict[str, str] | None = None, runner: Runner | None = None, out=None) -> int:
    env = env if env is not None else dict(os.environ)
    runner = runner or _default_runner
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    c = args.command
    if c == "status":
        return cmd_status(env, out)
    if c == "print-export-template":
        return cmd_print_export_template(out)
    if c == "write-env-file":
        return cmd_write_env_file(args, out)
    if c == "print-build-command":
        return cmd_print_build_command(env, out)
    if c == "print-full-operator-sequence":
        return cmd_print_full_operator_sequence(out)
    if c == "build-pack-from-env":
        return cmd_build_pack_from_env(env, runner, out)
    if c == "verify-pack-from-env":
        return cmd_verify_pack_from_env(env, runner, out)
    if c == "install-pack-from-env":
        return cmd_install_pack_from_env(env, runner, out)
    if c == "run-checks-from-env":
        return cmd_run_checks_from_env(runner, out)
    if c == "run-live-proof-from-env":
        return cmd_run_live_proof_from_env(env, runner, out)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
