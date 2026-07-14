from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest

from predator_mesh import staged_gate_common as sgc

_BASE = Path(sgc.ROOT) / "tools" / "operator_authority_appliance"
_spec = importlib.util.spec_from_file_location("operator_env_wizard", _BASE / "operator_env_wizard.py")
wiz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wiz)

PHRASE = wiz.REQUIRED_PHRASE
RISK = wiz.REQUIRED_RISK_ACK
INSTALL = wiz.INSTALL_CONFIRM_PHRASE
GOOD_ENV = {
    "DUMMY_OPERATOR_NAME": "chris", "DUMMY_OPERATOR_REASON": "controlled pilot",
    "DUMMY_OPERATOR_EXPIRES_AT": "2026-07-07T21:00:00Z", "DUMMY_AUTHORITY_PACK_DIR": "PACKDIR",
    "DUMMY_TYPED_APPROVAL": PHRASE, "DUMMY_RISK_ACK": RISK,
}


@pytest.fixture(autouse=True)
def _patch_runtime_approvals(tmp_path, monkeypatch):
    """Keep tests isolated from any real runtime/approvals installed in the repo."""
    monkeypatch.setattr(wiz._app, "DEFAULT_RUNTIME_APPROVALS", tmp_path / "runtime" / "approvals")


class FakeRunner:
    def __init__(self, rc=0, stdout="OK", stderr=""):
        self.calls = []
        self._rc, self._out, self._err = rc, stdout, stderr

    def __call__(self, cmd):
        self.calls.append(cmd)
        import subprocess
        return subprocess.CompletedProcess(cmd, self._rc, self._out, self._err)


def _run(argv, env=None, runner=None):
    buf = io.StringIO()
    rc = wiz.main(argv, env=env or {}, runner=runner or FakeRunner(), out=buf)
    return rc, buf.getvalue()


def _called_appliance(runner):
    return [" ".join(c) for c in runner.calls]


# --- status writes nothing ---
def test_status_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc, out = _run(["status"], env={})
    assert rc == 0 and "UNSET" in out
    assert list(tmp_path.iterdir()) == []


# --- print-export-template contains exact phrase + ack ---
def test_print_export_template_contains_phrase_and_ack():
    rc, out = _run(["print-export-template"])
    assert rc == 0 and PHRASE in out and RISK in out and INSTALL in out
    # env gate lines commented by default
    assert "# export DUMMY_LIVE_PROOF_MODE=1" in out


# --- write-env-file rejects fuzzy / broad / market / scale approvals ---
def test_write_env_file_rejects_fuzzy(tmp_path):
    rc, out = _run(["write-env-file", "--output", str(tmp_path / "e.env"), "--operator", "c", "--reason", "pilot",
                    "--expires-at", "t", "--typed-approval", "wrong", "--risk-ack", RISK])
    assert rc == wiz.EXIT_SAFETY and "APPROVAL_PHRASE_NOT_EXACT" in out
    assert not (tmp_path / "e.env").exists()


def test_write_env_file_rejects_broad_market_scale(tmp_path):
    for reason, code in [("grant full live trading", "BROAD_APPROVAL_REJECTED"),
                         ("pilot allow market order", "MARKET_ORDER_APPROVAL_REJECTED"),
                         ("pilot enable scale", "SCALE_OR_AUTONOMY_APPROVAL_REJECTED")]:
        rc, out = _run(["write-env-file", "--output", str(tmp_path / "e.env"), "--operator", "c", "--reason", reason,
                        "--expires-at", "t", "--typed-approval", PHRASE, "--risk-ack", RISK])
        assert rc == wiz.EXIT_SAFETY and code in out


def test_write_env_file_requires_operator_reason_expiry(tmp_path):
    rc, out = _run(["write-env-file", "--output", str(tmp_path / "e.env"), "--operator", "", "--reason", "",
                    "--expires-at", "", "--typed-approval", PHRASE, "--risk-ack", RISK])
    assert rc == wiz.EXIT_MISSING


# --- write-env-file accepts exact, no live-proof gate by default ---
def test_write_env_file_accepts_exact_no_gate_by_default(tmp_path):
    p = tmp_path / "op.env"
    rc, out = _run(["write-env-file", "--output", str(p), "--operator", "chris", "--reason", "controlled pilot",
                    "--expires-at", "2026-07-07T21:00:00Z", "--typed-approval", PHRASE, "--risk-ack", RISK])
    assert rc == 0 and p.exists()
    text = p.read_text(encoding="utf-8")
    assert "DUMMY_TYPED_APPROVAL=" in text
    assert "# DUMMY_LIVE_PROOF_MODE=1" in text and "\nDUMMY_LIVE_PROOF_MODE=1" not in text
    assert "# DUMMY_AUTHORITY_INSTALL_CONFIRM=" in text  # commented by default


def test_write_env_file_live_proof_gate_requires_confirmation(tmp_path):
    p = tmp_path / "op.env"
    rc, out = _run(["write-env-file", "--output", str(p), "--operator", "c", "--reason", "pilot", "--expires-at", "t",
                    "--typed-approval", PHRASE, "--risk-ack", RISK, "--include-live-proof-env-gate"])
    assert rc == wiz.EXIT_SAFETY and "LIVE_PROOF_ENV_GATE_CONFIRMATION_NOT_EXACT" in out
    assert not p.exists()
    rc2, _ = _run(["write-env-file", "--output", str(p), "--operator", "c", "--reason", "pilot", "--expires-at", "t",
                   "--typed-approval", PHRASE, "--risk-ack", RISK, "--include-live-proof-env-gate",
                   "--confirm-live-proof-env-gate", wiz.CONFIRM_LIVE_PROOF_ENV_GATE])
    assert rc2 == 0
    assert "\nDUMMY_LIVE_PROOF_MODE=1" in p.read_text(encoding="utf-8")


# --- print-build-command reports missing vars ---
def test_print_build_command_reports_missing():
    rc, out = _run(["print-build-command"], env={})
    assert rc == wiz.EXIT_MISSING and "MISSING_VARS" in out


def test_print_build_command_full_env():
    rc, out = _run(["print-build-command"], env=GOOD_ENV)
    assert rc == 0 and "build-authority-pack" in out and PHRASE in out


# --- build-pack-from-env fails closed when vars missing, calls appliance when exact ---
def test_build_pack_from_env_fails_closed_missing():
    r = FakeRunner()
    rc, out = _run(["build-pack-from-env"], env={}, runner=r)
    assert rc == wiz.EXIT_MISSING and r.calls == []


def test_build_pack_from_env_calls_appliance(tmp_path):
    env = dict(GOOD_ENV)
    env["DUMMY_AUTHORITY_PACK_DIR"] = str(tmp_path / "pack")
    r = FakeRunner()
    rc, out = _run(["build-pack-from-env"], env=env, runner=r)
    assert rc == 0
    joined = _called_appliance(r)[0]
    assert "operator_authority_appliance.py build-authority-pack" in joined
    assert str(tmp_path / "pack") in joined
    assert not any("execute_once" in c for c in _called_appliance(r))


# --- verify-pack-from-env calls existing verify ---
def test_verify_pack_from_env_calls_verify():
    r = FakeRunner()
    rc, out = _run(["verify-pack-from-env"], env={"DUMMY_AUTHORITY_PACK_DIR": "PACK"}, runner=r)
    assert rc == 0 and "verify-authority-pack" in _called_appliance(r)[0]


# --- install-pack-from-env requires exact install confirmation ---
def test_install_pack_from_env_requires_confirmation():
    r = FakeRunner()
    rc, out = _run(["install-pack-from-env"], env={"DUMMY_AUTHORITY_PACK_DIR": "PACK"}, runner=r)
    assert rc == wiz.EXIT_MISSING and r.calls == []
    r2 = FakeRunner()
    rc2, out2 = _run(["install-pack-from-env"], env={"DUMMY_AUTHORITY_PACK_DIR": "PACK", "DUMMY_AUTHORITY_INSTALL_CONFIRM": INSTALL}, runner=r2)
    assert rc2 == 0 and "install-authority-pack" in _called_appliance(r2)[0]


# --- run-checks-from-env never calls live-proof ---
def test_run_checks_from_env_no_live_proof():
    r = FakeRunner()
    rc, out = _run(["run-checks-from-env"], runner=r)
    assert rc == 0 and "run-authority-checks" in _called_appliance(r)[0]
    assert not any("run-live-proof-once" in c for c in _called_appliance(r))


# --- run-live-proof-from-env blocks without env gate, calls only appliance when exact ---
def test_run_live_proof_from_env_blocks_without_env_gate():
    r = FakeRunner()
    rc, out = _run(["run-live-proof-from-env"], env={}, runner=r)
    assert rc == wiz.EXIT_MISSING and "BLOCKED_ENV_GATE_ABSENT" in out and r.calls == []


def test_run_live_proof_from_env_calls_only_appliance_when_gate_exact():
    r = FakeRunner()
    env = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}
    rc, out = _run(["run-live-proof-from-env"], env=env, runner=r)
    assert rc == 0
    calls = _called_appliance(r)
    assert len(calls) == 1 and "run-live-proof-once" in calls[0]
    # Never calls the Dummy execute-once script directly.
    assert not any("run_dummy_execute_once_final_proof_v7.py" in c for c in calls)


# --- no repo runtime/approvals created by wizard operations in tests ---
def test_wizard_never_creates_repo_runtime_approvals(tmp_path):
    _run(["status"], env={})
    _run(["build-pack-from-env"], env={}, runner=FakeRunner())
    assert wiz._app.DEFAULT_RUNTIME_APPROVALS.exists() is False
