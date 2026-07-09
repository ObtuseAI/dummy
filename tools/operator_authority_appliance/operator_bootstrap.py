"""Operator-side bootstrap orchestrator for the DUMMY authority appliance.

One-stop operator helper that chains the EXISTING tools (operator_env_wizard + operator_authority_appliance)
to remove clerical friction. It never adds Dummy architecture, never self-authorizes Dummy, never creates
runtime/approvals by default, never modifies live-submit/caps, never injects a broker adapter, never contacts
a broker, never calls the Dummy execute-once script directly, and never runs live-proof without the exact env
gate. All validation is delegated to the existing tools; this module only sequences them and reports state.

Exit codes: 0 success · 2 missing operator input · 3 subprocess failure · 4 safety rejection.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Callable

BASE = Path(__file__).resolve().parent
DUMMY_ROOT = BASE.parents[1]
WIZARD_CLI = BASE / "operator_env_wizard.py"
APPLIANCE_CLI = BASE / "operator_authority_appliance.py"
STOP_RULE_SCRIPT = "scripts/run_dummy_proof_starvation_stop_rule.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_wiz = _load("operator_env_wizard", WIZARD_CLI)
_app = _load("operator_authority_appliance", APPLIANCE_CLI)

REQUIRED_PHRASE = _wiz.REQUIRED_PHRASE
REQUIRED_RISK_ACK = _wiz.REQUIRED_RISK_ACK
INSTALL_CONFIRM_PHRASE = _wiz.INSTALL_CONFIRM_PHRASE
CONFIRM_LIVE_PROOF_ENV_GATE = _wiz.CONFIRM_LIVE_PROOF_ENV_GATE
ENV_MODE = _wiz.ENV_MODE
ENV_ACK = _wiz.ENV_ACK
BUILD_VARS = _wiz.BUILD_VARS
DEFAULT_PACK_DIR = _wiz.DEFAULT_PACK_DIR
DEFAULT_TEMPLATE_PATH = "operator_authority_pack/operator_authority.env.template"

EXIT_OK, EXIT_MISSING, EXIT_SUBPROC, EXIT_SAFETY = 0, 2, 3, 4

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


def _default_runner(cmd: list[str]) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(cmd, cwd=str(DUMMY_ROOT), capture_output=True, text=True)  # shell=False


def _wiz_cmd(*a: str) -> list[str]:
    return [sys.executable, str(WIZARD_CLI), *a]


def _shell(cmd: list[str], runner: Runner, out) -> int:
    proc = runner(cmd)
    if proc.stdout:
        print(proc.stdout.rstrip(), file=out)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr.rstrip()[:500], file=out)
        return EXIT_SUBPROC if proc.returncode == EXIT_SUBPROC or proc.returncode not in (EXIT_MISSING, EXIT_SAFETY) else proc.returncode
    return EXIT_OK


def _missing_build_vars(env: dict[str, str]) -> list[str]:
    return [v for v in BUILD_VARS if not env.get(v)]


def _env_gate(env: dict[str, str]) -> bool:
    return env.get(ENV_MODE[0]) == ENV_MODE[1] and env.get(ENV_ACK[0]) == ENV_ACK[1]


# ----------------------------- commands -----------------------------

def cmd_status(env: dict[str, str], runner: Runner, out) -> int:
    seal = _app.command_seal_status()
    gate = _env_gate(env)
    missing = _missing_build_vars(env)
    stop = runner([sys.executable, STOP_RULE_SCRIPT])
    stop_ok = "PASS_PROOF_STARVATION_STOP_RULE_ACTIVE" in (stop.stdout or "")
    print("# DUMMY operator bootstrap status (read-only)", file=out)
    print("| blocker | state |", file=out)
    print(f"| build_env_vars_missing | {','.join(missing) or 'NONE'} |", file=out)
    print(f"| command_seal | {seal} |", file=out)
    print(f"| env_gate_present | {gate} |", file=out)
    print(f"| install_confirm_present | {env.get('DUMMY_AUTHORITY_INSTALL_CONFIRM') == INSTALL_CONFIRM_PHRASE} |", file=out)
    print(f"| runtime_approvals_exists | {_app.DEFAULT_RUNTIME_APPROVALS.exists()} |", file=out)
    print(f"| proof_lock_used | {_app.proof_lock_exists()} |", file=out)
    print(f"| proof_starvation_stop_rule_active | {stop_ok} |", file=out)
    return EXIT_OK


def cmd_generate_env(args, out) -> int:
    argv = ["write-env-file", "--output", args.output, "--operator", args.operator, "--reason", args.reason,
            "--expires-at", args.expires_at, "--authority-pack-dir", args.authority_pack_dir,
            "--typed-approval", args.typed_approval, "--risk-ack", args.risk_ack]
    if args.include_install_confirmation:
        argv.append("--include-install-confirmation")
    if args.include_live_proof_env_gate:
        argv.append("--include-live-proof-env-gate")
        argv += ["--confirm-live-proof-env-gate", args.confirm_live_proof_env_gate]
    return _wiz.main(argv, env={}, out=out)  # delegates all validation to the wizard (no duplicated logic)


def cmd_generate_env_template(args, out) -> int:
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NOT_APPROVAL — operator env TEMPLATE. Editing this does not authorize anything.",
        "# Fill placeholders, save as a real .env, then `source` it. Dummy still enforces every gate.",
        'DUMMY_OPERATOR_NAME="<operator name>"',
        'DUMMY_OPERATOR_REASON="<reason for one controlled production pilot>"',
        'DUMMY_OPERATOR_EXPIRES_AT="<ISO-8601 expiry timestamp>"',
        f'DUMMY_AUTHORITY_PACK_DIR="{DEFAULT_PACK_DIR}"',
        f'DUMMY_TYPED_APPROVAL="{REQUIRED_PHRASE}"',
        f'DUMMY_RISK_ACK="{REQUIRED_RISK_ACK}"',
        f'# DUMMY_AUTHORITY_INSTALL_CONFIRM="{INSTALL_CONFIRM_PHRASE}"',
        f"# {ENV_MODE[0]}={ENV_MODE[1]}",
        f"# {ENV_ACK[0]}={ENV_ACK[1]}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE_ENV_TEMPLATE (NOT_APPROVAL): {path}", file=out)
    return EXIT_OK


def cmd_build_and_verify_pack(env: dict[str, str], runner: Runner, out) -> int:
    missing = _missing_build_vars(env)
    if missing:
        print("MISSING_VARS: " + ", ".join(missing), file=out)
        return EXIT_MISSING
    rc = _shell(_wiz_cmd("build-pack-from-env"), runner, out)
    if rc != EXIT_OK:
        print("BUILD_FAILED", file=out)
        return rc
    rc = _shell(_wiz_cmd("verify-pack-from-env"), runner, out)
    if rc != EXIT_OK:
        print("VERIFY_FAILED", file=out)
    return rc


def cmd_prepare_install_command(env: dict[str, str], runner: Runner, out) -> int:
    if not env.get("DUMMY_AUTHORITY_PACK_DIR"):
        print("MISSING_VARS: DUMMY_AUTHORITY_PACK_DIR", file=out)
        return EXIT_MISSING
    _shell(_wiz_cmd("verify-pack-from-env"), runner, out)
    print("# To install (creates runtime/approvals via appliance ONLY):", file=out)
    print(f'export DUMMY_AUTHORITY_INSTALL_CONFIRM="{INSTALL_CONFIRM_PHRASE}"', file=out)
    print("python tools/operator_authority_appliance/operator_env_wizard.py install-pack-from-env", file=out)
    return EXIT_OK


def cmd_install_if_confirmed(env: dict[str, str], runner: Runner, out) -> int:
    if not env.get("DUMMY_AUTHORITY_PACK_DIR"):
        print("MISSING_VARS: DUMMY_AUTHORITY_PACK_DIR", file=out)
        return EXIT_MISSING
    if env.get("DUMMY_AUTHORITY_INSTALL_CONFIRM") != INSTALL_CONFIRM_PHRASE:
        print("INSTALL_CONFIRMATION_REQUIRED (exact): " + INSTALL_CONFIRM_PHRASE, file=out)
        return EXIT_MISSING
    return _shell(_wiz_cmd("install-pack-from-env"), runner, out)


def cmd_authority_checks(runner: Runner, out) -> int:
    rc = _shell(_wiz_cmd("run-checks-from-env"), runner, out)
    seal = _app.command_seal_status()
    if seal == "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT":
        print("BLOCKER: command_seal READY -> env gate required", file=out)
    else:
        print(f"BLOCKER: {seal}", file=out)
    return rc


def cmd_prepare_live_proof_command(env: dict[str, str], runner: Runner, out) -> int:
    cmd_authority_checks(runner, out)
    seal = _app.command_seal_status()
    if seal == "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT" and not _env_gate(env):
        print("# Command seal ready — arm env gate then run live-proof:", file=out)
        print(f"export {ENV_MODE[0]}={ENV_MODE[1]}", file=out)
        print(f"export {ENV_ACK[0]}={ENV_ACK[1]}", file=out)
        print("python tools/operator_authority_appliance/operator_env_wizard.py run-live-proof-from-env", file=out)
    else:
        print(f"NOT_READY_FOR_LIVE_PROOF: seal={seal} env_gate={_env_gate(env)}", file=out)
    return EXIT_OK


def cmd_run_live_proof_if_ready(env: dict[str, str], runner: Runner, out) -> int:
    if not _env_gate(env):
        print(f"BLOCKED_ENV_GATE_ABSENT: require {ENV_MODE[0]}={ENV_MODE[1]} {ENV_ACK[0]}={ENV_ACK[1]}", file=out)
        return EXIT_MISSING
    return _shell(_wiz_cmd("run-live-proof-from-env"), runner, out)


def cmd_max_progress(env: dict[str, str], runner: Runner, out) -> int:
    print("=== bootstrap max-progress (no live/broker/self-authorization) ===", file=out)
    cmd_status(env, runner, out)
    tmpl = Path(env.get("DUMMY_BOOTSTRAP_TEMPLATE_PATH", DEFAULT_TEMPLATE_PATH))
    ns = argparse.Namespace(output=str(tmpl))
    cmd_generate_env_template(ns, out)
    missing = _missing_build_vars(env)
    if missing:
        print("STOP: build env vars missing -> template written only. Next: fill env then build-and-verify-pack.", file=out)
        print("VERDICT: OPERATOR_ENV_REQUIRED", file=out)
        return EXIT_OK
    if cmd_build_and_verify_pack(env, runner, out) != EXIT_OK:
        print("VERDICT: REPAIR_REQUIRED", file=out)
        return EXIT_OK
    if env.get("DUMMY_AUTHORITY_INSTALL_CONFIRM") == INSTALL_CONFIRM_PHRASE:
        cmd_install_if_confirmed(env, runner, out)
    else:
        print("STOP: install confirmation absent (external live-submit/caps/adapter also required).", file=out)
        print("VERDICT: AUTHORITY_PACK_VERIFIED_INSTALL_CONFIRMATION_REQUIRED", file=out)
        return EXIT_OK
    cmd_authority_checks(runner, out)
    if not _env_gate(env):
        cmd_prepare_live_proof_command(env, runner, out)
        print("VERDICT: COMMAND_SEAL_READY_ENV_GATE_REQUIRED", file=out)
        return EXIT_OK
    return cmd_run_live_proof_if_ready(env, runner, out)


# ----------------------------- CLI -----------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Operator-side bootstrap orchestrator for the Dummy authority appliance (fail-closed).")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("status", "build-and-verify-pack", "prepare-install-command", "install-if-confirmed",
                 "authority-checks", "prepare-live-proof-command", "run-live-proof-if-ready", "max-progress"):
        sub.add_parser(name)
    g = sub.add_parser("generate-env")
    g.add_argument("--output", required=True)
    g.add_argument("--operator", required=True)
    g.add_argument("--reason", required=True)
    g.add_argument("--expires-at", required=True)
    g.add_argument("--authority-pack-dir", default=DEFAULT_PACK_DIR)
    g.add_argument("--typed-approval", required=True)
    g.add_argument("--risk-ack", required=True)
    g.add_argument("--include-install-confirmation", action="store_true")
    g.add_argument("--include-live-proof-env-gate", action="store_true")
    g.add_argument("--confirm-live-proof-env-gate", default="")
    t = sub.add_parser("generate-env-template")
    t.add_argument("--output", default=DEFAULT_TEMPLATE_PATH)
    return p


def main(argv: list[str] | None = None, *, env: dict[str, str] | None = None, runner: Runner | None = None, out=None) -> int:
    import os
    env = env if env is not None else dict(os.environ)
    runner = runner or _default_runner
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    c = args.command
    if c == "status":
        return cmd_status(env, runner, out)
    if c == "generate-env":
        return cmd_generate_env(args, out)
    if c == "generate-env-template":
        return cmd_generate_env_template(args, out)
    if c == "build-and-verify-pack":
        return cmd_build_and_verify_pack(env, runner, out)
    if c == "prepare-install-command":
        return cmd_prepare_install_command(env, runner, out)
    if c == "install-if-confirmed":
        return cmd_install_if_confirmed(env, runner, out)
    if c == "authority-checks":
        return cmd_authority_checks(runner, out)
    if c == "prepare-live-proof-command":
        return cmd_prepare_live_proof_command(env, runner, out)
    if c == "run-live-proof-if-ready":
        return cmd_run_live_proof_if_ready(env, runner, out)
    if c == "max-progress":
        return cmd_max_progress(env, runner, out)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
