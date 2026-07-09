from __future__ import annotations

import importlib.util
import io
import subprocess
from pathlib import Path

import pytest

from predator_mesh import staged_gate_common as sgc

_BASE = Path(sgc.ROOT) / "tools" / "operator_authority_appliance"
_spec = importlib.util.spec_from_file_location("operator_bootstrap", _BASE / "operator_bootstrap.py")
bs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bs)

PHRASE = bs.REQUIRED_PHRASE
RISK = bs.REQUIRED_RISK_ACK
INSTALL = bs.INSTALL_CONFIRM_PHRASE
GOOD_ENV = {
    "DUMMY_OPERATOR_NAME": "chris", "DUMMY_OPERATOR_REASON": "controlled pilot",
    "DUMMY_OPERATOR_EXPIRES_AT": "2026-07-08T21:00:00Z", "DUMMY_AUTHORITY_PACK_DIR": "PACK",
    "DUMMY_TYPED_APPROVAL": PHRASE, "DUMMY_RISK_ACK": RISK,
}


@pytest.fixture(autouse=True)
def _patch_runtime_approvals(tmp_path, monkeypatch):
    """Keep tests isolated from any real runtime/approvals installed in the repo."""
    monkeypatch.setattr(bs._app, "DEFAULT_RUNTIME_APPROVALS", tmp_path / "runtime" / "approvals")


class FakeRunner:
    def __init__(self, rc=0, stdout="OK"):
        self.calls = []
        self._rc, self._out = rc, stdout

    def __call__(self, cmd):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self._rc, self._out, "")


def _run(argv, env=None, runner=None):
    buf = io.StringIO()
    rc = bs.main(argv, env=env or {}, runner=runner or FakeRunner(), out=buf)
    return rc, buf.getvalue()


def _joined(runner):
    return [" ".join(str(x) for x in c) for c in runner.calls]


# --- status writes nothing ---
def test_status_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc, out = _run(["status"], env={}, runner=FakeRunner(stdout="PASS_PROOF_STARVATION_STOP_RULE_ACTIVE"))
    assert rc == 0 and "proof_starvation_stop_rule_active" in out
    assert list(tmp_path.iterdir()) == []


# --- generate-env-template creates only NOT_APPROVAL template ---
def test_generate_env_template_not_approval(tmp_path):
    p = tmp_path / "op.env.template"
    rc, out = _run(["generate-env-template", "--output", str(p)])
    assert rc == 0 and p.exists()
    text = p.read_text(encoding="utf-8")
    assert "NOT_APPROVAL" in text and PHRASE in text
    assert "# DUMMY_LIVE_PROOF_MODE=1" in text  # gate commented
    assert "# DUMMY_AUTHORITY_INSTALL_CONFIRM=" in text  # install commented


# --- generate-env rejects fuzzy / broad / market / scale approvals ---
def test_generate_env_rejects_fuzzy(tmp_path):
    rc, out = _run(["generate-env", "--output", str(tmp_path / "e"), "--operator", "c", "--reason", "pilot",
                    "--expires-at", "t", "--typed-approval", "wrong", "--risk-ack", RISK])
    assert rc == bs.EXIT_SAFETY and not (tmp_path / "e").exists()


def test_generate_env_rejects_broad_market_scale(tmp_path):
    for reason in ("grant full live trading", "pilot allow market order", "pilot enable autonomy"):
        rc, out = _run(["generate-env", "--output", str(tmp_path / "e"), "--operator", "c", "--reason", reason,
                        "--expires-at", "t", "--typed-approval", PHRASE, "--risk-ack", RISK])
        assert rc == bs.EXIT_SAFETY


# --- generate-env accepts exact into temp env file ---
def test_generate_env_accepts_exact(tmp_path):
    p = tmp_path / "op.env"
    rc, out = _run(["generate-env", "--output", str(p), "--operator", "chris", "--reason", "controlled pilot",
                    "--expires-at", "2026-07-08T21:00:00Z", "--typed-approval", PHRASE, "--risk-ack", RISK])
    assert rc == 0 and p.exists()
    assert "DUMMY_TYPED_APPROVAL=" in p.read_text(encoding="utf-8")


# --- build-and-verify-pack blocks when env missing; calls wizard when present ---
def test_build_and_verify_blocks_when_env_missing():
    r = FakeRunner()
    rc, out = _run(["build-and-verify-pack"], env={}, runner=r)
    assert rc == bs.EXIT_MISSING and r.calls == []


def test_build_and_verify_calls_wizard_when_env_present():
    r = FakeRunner()
    rc, out = _run(["build-and-verify-pack"], env=GOOD_ENV, runner=r)
    assert rc == 0
    j = _joined(r)
    assert any("build-pack-from-env" in c for c in j) and any("verify-pack-from-env" in c for c in j)
    assert not any("run-live-proof" in c or "execute_once" in c for c in j)


# --- prepare-install-command does not install ---
def test_prepare_install_command_no_install():
    r = FakeRunner()
    rc, out = _run(["prepare-install-command"], env={"DUMMY_AUTHORITY_PACK_DIR": "PACK"}, runner=r)
    assert rc == 0 and INSTALL in out
    assert not any("install-pack-from-env" in c for c in _joined(r))


# --- install-if-confirmed blocks without exact confirmation ---
def test_install_if_confirmed_blocks_without_confirmation():
    r = FakeRunner()
    rc, out = _run(["install-if-confirmed"], env={"DUMMY_AUTHORITY_PACK_DIR": "PACK"}, runner=r)
    assert rc == bs.EXIT_MISSING and r.calls == []
    r2 = FakeRunner()
    rc2, out2 = _run(["install-if-confirmed"], env={"DUMMY_AUTHORITY_PACK_DIR": "PACK", "DUMMY_AUTHORITY_INSTALL_CONFIRM": INSTALL}, runner=r2)
    assert rc2 == 0 and any("install-pack-from-env" in c for c in _joined(r2))


# --- authority-checks does not run live proof ---
def test_authority_checks_no_live_proof():
    r = FakeRunner()
    rc, out = _run(["authority-checks"], runner=r)
    j = _joined(r)
    assert any("run-checks-from-env" in c for c in j)
    assert not any("run-live-proof" in c for c in j)


# --- prepare-live-proof-command does not run live proof ---
def test_prepare_live_proof_command_no_run():
    r = FakeRunner()
    rc, out = _run(["prepare-live-proof-command"], env={}, runner=r)
    assert not any("run-live-proof-from-env" in c for c in _joined(r))


# --- run-live-proof-if-ready blocks without env gate; calls wizard only when gate exact ---
def test_run_live_proof_if_ready_blocks_without_env_gate():
    r = FakeRunner()
    rc, out = _run(["run-live-proof-if-ready"], env={}, runner=r)
    assert rc == bs.EXIT_MISSING and "BLOCKED_ENV_GATE_ABSENT" in out and r.calls == []


def test_run_live_proof_if_ready_calls_wizard_when_gate_exact():
    r = FakeRunner()
    env = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}
    rc, out = _run(["run-live-proof-if-ready"], env=env, runner=r)
    assert rc == 0
    j = _joined(r)
    assert len(j) == 1 and "run-live-proof-from-env" in j[0]
    assert not any("run_dummy_execute_once_final_proof_v7.py" in c for c in j)


# --- max-progress with no env creates template only, no runtime/approvals ---
def test_max_progress_no_env_template_only(tmp_path):
    tmpl = tmp_path / "operator_authority_pack" / "operator_authority.env.template"
    env = {"DUMMY_BOOTSTRAP_TEMPLATE_PATH": str(tmpl)}
    r = FakeRunner(stdout="PASS_PROOF_STARVATION_STOP_RULE_ACTIVE")
    rc, out = _run(["max-progress"], env=env, runner=r)
    assert rc == 0 and "OPERATOR_ENV_REQUIRED" in out
    assert tmpl.exists() and "NOT_APPROVAL" in tmpl.read_text(encoding="utf-8")
    # No pack build / live-proof attempted with no env.
    assert not any("run-live-proof" in c for c in _joined(r))
    # No repo runtime/approvals created.
    assert bs._app.DEFAULT_RUNTIME_APPROVALS.exists() is False


# --- bootstrap never creates repo runtime/approvals ---
def test_bootstrap_never_creates_repo_runtime_approvals():
    _run(["status"], env={}, runner=FakeRunner(stdout="PASS"))
    _run(["build-and-verify-pack"], env={}, runner=FakeRunner())
    assert bs._app.DEFAULT_RUNTIME_APPROVALS.exists() is False
