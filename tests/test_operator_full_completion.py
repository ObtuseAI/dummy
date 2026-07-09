from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from pathlib import Path

import pytest

from predator_mesh import staged_gate_common as sgc

_BASE = Path(sgc.ROOT) / "tools" / "operator_authority_appliance"
_spec = importlib.util.spec_from_file_location("operator_full_completion", _BASE / "operator_full_completion.py")
fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc)

PHRASE = fc.REQUIRED_PHRASE
RISK = fc.REQUIRED_RISK_ACK
INSTALL = fc.INSTALL_CONFIRM_PHRASE
GATE = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}


@pytest.fixture(autouse=True)
def _patch_runtime_approvals(tmp_path, monkeypatch):
    """Keep tests isolated from any real runtime/approvals installed in the repo."""
    monkeypatch.setattr(fc._app, "DEFAULT_RUNTIME_APPROVALS", tmp_path / "runtime" / "approvals")


@pytest.fixture(autouse=True)
def _no_dotenv_load(monkeypatch):
    """Prevent one-shot commands from reading real .env credentials during tests."""
    monkeypatch.setattr(fc, "_load_dotenv_for_one_shot", lambda: {})


@pytest.fixture(autouse=True)
def _no_second_proof_draft(monkeypatch):
    """Keep legacy one-shot-check tests isolated from any repo second-proof draft."""
    monkeypatch.setattr(fc, "_second_proof_authority_state", lambda: {"state": "none"})


class FakeRunner:
    def __init__(self, rc=0, stdout="OK"):
        self.calls = []
        self._rc, self._out = rc, stdout

    def __call__(self, cmd):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self._rc, self._out, "")


def _run(argv, env=None, runner=None):
    buf = io.StringIO()
    rc = fc.main(argv, env=env or {}, runner=runner or FakeRunner(), out=buf)
    return rc, buf.getvalue()


def _joined(runner):
    return [" ".join(str(x) for x in c) for c in runner.calls]


def _prep_args(pack_dir, **over):
    a = ["one-shot-prepare", "--operator", "chris", "--reason", "controlled pilot",
         "--expires-at", "2026-07-08T21:00:00Z", "--authority-pack-dir", str(pack_dir),
         "--typed-approval", PHRASE, "--risk-ack", RISK]
    return a


# --- status read-only ---
def test_status_read_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc, out = _run(["status"], env={}, runner=FakeRunner(stdout="PASS_PROOF_STARVATION_STOP_RULE_ACTIVE"))
    assert rc == 0 and "first_hard_blocker=MISSING_OPERATOR_VALUES" in out
    assert list(tmp_path.iterdir()) == []


# --- doctor read-only, writes only its report, no live proof ---
def test_doctor_read_only_writes_report(tmp_path):
    env = {"DUMMY_FULLCOMP_ARTIFACTS_DIR": str(tmp_path / "art")}
    r = FakeRunner(stdout="PASS_PROOF_STARVATION_STOP_RULE_ACTIVE")
    rc, out = _run(["doctor"], env=env, runner=r)
    assert rc == 0
    rep = tmp_path / "art" / "operator_full_completion_doctor.json"
    assert rep.exists() and "first_hard_blocker" in rep.read_text(encoding="utf-8")
    assert not any("run-live-proof" in c for c in _joined(r))
    assert fc._app.DEFAULT_RUNTIME_APPROVALS.exists() is False


# --- one-shot-prepare rejects fuzzy / broad / market / scale ---
def test_one_shot_prepare_rejects_fuzzy(tmp_path):
    a = _prep_args(tmp_path / "pack"); a[a.index("--typed-approval") + 1] = "wrong"
    rc, out = _run(a)
    assert rc == fc.EXIT_SAFETY


def test_one_shot_prepare_rejects_broad_market_scale(tmp_path):
    for reason in ("grant full live trading", "pilot allow market order", "pilot enable scale"):
        a = _prep_args(tmp_path / "pack"); a[a.index("--reason") + 1] = reason
        rc, out = _run(a)
        assert rc == fc.EXIT_SAFETY


# --- one-shot-prepare exact: writes env + pack in temp, no runtime/approvals ---
def test_one_shot_prepare_exact_writes_pack(tmp_path):
    pack = tmp_path / "pack"
    rc, out = _run(_prep_args(pack))
    assert rc == 0 and "OPERATOR_AUTHORITY_PACK_READY_EXTERNAL_CONFIG_REQUIRED" in out
    for name in fc.PACK_FILES:
        assert (pack / name).exists()
    assert (pack / "operator_authority.env").exists()
    assert fc._app.DEFAULT_RUNTIME_APPROVALS.exists() is False


# --- one-shot-install rejects missing confirmation; installs to temp runtime with exact ---
def test_one_shot_install_rejects_missing_confirmation():
    r = FakeRunner()
    rc, out = _run(["one-shot-install", "--authority-pack-dir", "PACK", "--operator-confirm-install", "nope"], runner=r)
    assert rc == fc.EXIT_MISSING and r.calls == []


def test_one_shot_install_calls_bootstrap_with_exact(monkeypatch, tmp_path):
    # Bootstrap install-if-confirmed shells to wizard install-pack-from-env; capture via runner.
    r = FakeRunner()
    rc, out = _run(["one-shot-install", "--authority-pack-dir", "PACK", "--operator-confirm-install", INSTALL], runner=r)
    assert rc == 0 and any("install-pack-from-env" in c for c in _joined(r))


# --- one-shot-check does not call live proof ---
def test_one_shot_check_no_live_proof():
    r = FakeRunner()
    rc, out = _run(["one-shot-check"], env={}, runner=r)
    assert not any("run-live-proof" in c for c in _joined(r))
    assert "BLOCKED_" in out


def test_one_shot_check_reports_missing_credentials():
    r = FakeRunner()
    rc, out = _run(["one-shot-check"], env={}, runner=r)
    assert rc == 0
    assert "BLOCKED_MISSING_KALSHI_CREDENTIALS" in out


def test_one_shot_check_reports_live_submit_caps_blocker(monkeypatch):
    monkeypatch.setenv("KALSHI_API_KEY_ID", "test")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", "test-key")
    r = FakeRunner()
    rc, out = _run(["one-shot-check"], env={}, runner=r)
    assert rc == 0
    assert "BLOCKED_LIVE_SUBMIT_CAPS" in out


def test_one_shot_check_reports_command_seal_blocked(monkeypatch):
    monkeypatch.setenv("KALSHI_API_KEY_ID", "test")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", "test-key")
    # Stage a valid live-submit config and strict caps.
    future = "2099-01-01T00:00:00Z"
    live_submit = {
        "enabled": True,
        "operator": "chris",
        "reason": "test",
        "timestamp": future,
        "expiry": future,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "explicit_acknowledgement": fc.LIVE_SUBMIT_REQUIRED_ACK,
    }
    monkeypatch.setattr(fc, "_load_json", lambda p: live_submit if "live_submit" in str(p) else {})
    monkeypatch.setattr(fc, "_caps_are_strict", lambda: True)
    monkeypatch.setattr(fc, "_descriptor_staged", lambda: True)
    r = FakeRunner()
    rc, out = _run(["one-shot-check"], env={}, runner=r)
    assert rc == 0
    assert "BLOCKED_COMMAND_SEAL" in out


# --- enable-one-proof-live-submit writes safe config ---
def test_enable_one_proof_live_submit_requires_exact_confirmation():
    rc, out = _run([
        "enable-one-proof-live-submit",
        "--operator", "chris",
        "--reason", "one controlled proof",
        "--expires-at", "2099-01-01T00:00:00Z",
        "--typed-confirmation", "wrong",
    ])
    assert rc == fc.EXIT_MISSING


def test_enable_one_proof_live_submit_writes_atomic_config_with_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "LIVE_SUBMIT_PATH", tmp_path / "configs" / "live_submit.json")
    monkeypatch.setattr(fc, "ADAPTER_DESCRIPTOR_PATH", tmp_path / "descriptor.json")
    monkeypatch.setattr(fc, "CAPS_PATH", tmp_path / "configs" / "caps.json")
    rc, out = _run([
        "enable-one-proof-live-submit",
        "--operator", "chris",
        "--reason", "one controlled proof",
        "--expires-at", "2099-01-01T00:00:00Z",
        "--typed-confirmation", fc.LIVE_SUBMIT_TYPED_CONFIRMATION,
    ])
    assert rc == 0
    assert "LIVE_SUBMIT_ENABLED_ONE_PROOF" in out
    written = json.loads((tmp_path / "configs" / "live_submit.json").read_text())
    assert written["enabled"] is True
    assert written["proof_scope"] == "one_controlled_proof"
    assert written["requires_command_seal"] is True
    assert written["requires_livebrokerfirewall"] is True
    assert written["requires_limit_order"] is True
    assert written["market_orders_allowed"] is False
    assert written["max_order_count"] == 1
    assert written["scale_enabled"] is False
    assert written["autonomy_enabled"] is False


# --- disable-live-submit relocks safely ---
def test_disable_live_submit_relocks(tmp_path, monkeypatch):
    path = tmp_path / "configs" / "live_submit.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"enabled": True, "explicit_acknowledgement": "ack"}))
    monkeypatch.setattr(fc, "LIVE_SUBMIT_PATH", path)
    rc, out = _run(["disable-live-submit"])
    assert rc == 0
    assert "LIVE_SUBMIT_DISABLED" in out
    written = json.loads(path.read_text())
    assert written["enabled"] is False
    assert "explicit_acknowledgement" not in written


# --- one-shot-live blocks without env gate ---
def test_one_shot_live_blocks_without_env_gate():
    r = FakeRunner()
    rc, out = _run(["one-shot-live"], env={}, runner=r)
    assert rc == fc.EXIT_MISSING and "BLOCKED_ENV_GATE_ABSENT" in out and r.calls == []


# --- one-shot-live blocks if not armable (seal blocked) even with env gate ---
def test_one_shot_live_blocks_if_not_armable(monkeypatch):
    monkeypatch.setattr(fc, "_seal_status", lambda: "PARTIAL_COMMAND_SEAL_BLOCKED_AUTHORITY_ABSENT")
    r = FakeRunner()
    rc, out = _run(["one-shot-live"], env=GATE, runner=r)
    assert rc == fc.EXIT_EXTERNAL and "BLOCKED_NOT_ARMABLE" in out and r.calls == []


# --- one-shot-live calls only appliance run-live-proof-once when gate + checks ready ---
def test_one_shot_live_calls_only_appliance_when_ready(monkeypatch):
    monkeypatch.setattr(fc, "_seal_status", lambda: fc.SEAL_READY)
    monkeypatch.setattr(fc, "_proof_lock", lambda: False)
    r = FakeRunner()
    rc, out = _run(["one-shot-live"], env=GATE, runner=r)
    assert rc == 0
    j = _joined(r)
    assert any("run-live-proof-from-env" in c for c in j)
    assert not any("run_dummy_execute_once_final_proof_v7.py" in c for c in j)


def test_one_shot_live_blocks_if_proof_lock_used(monkeypatch):
    monkeypatch.setattr(fc, "_seal_status", lambda: fc.SEAL_READY)
    monkeypatch.setattr(fc, "_proof_lock", lambda: True)
    r = FakeRunner()
    rc, out = _run(["one-shot-live"], env=GATE, runner=r)
    assert rc == fc.EXIT_MISSING and "PROOF_LOCK_ALREADY_USED" in out and r.calls == []


# --- full-auto with missing env → OPERATOR_INPUT_REQUIRED ---
def test_full_auto_missing_env_input_required(tmp_path):
    env = {"DUMMY_FULLCOMP_ARTIFACTS_DIR": str(tmp_path / "art")}
    rc, out = _run(["full-auto"], env=env, runner=FakeRunner(stdout="PASS_PROOF_STARVATION_STOP_RULE_ACTIVE"))
    assert rc == fc.EXIT_MISSING and "OPERATOR_INPUT_REQUIRED" in out


# --- full-auto with env present but no external config stops before live proof ---
def test_full_auto_env_present_stops_before_live(monkeypatch):
    env = {v: "x" for v in fc.BUILD_VARS}
    env["DUMMY_AUTHORITY_PACK_DIR"] = "PACK"
    r = FakeRunner()  # build-and-verify faked ok
    rc, out = _run(["full-auto"], env=env, runner=r)
    assert "VERDICT:" in out
    assert not any("run-live-proof-from-env" in c for c in _joined(r))
    assert fc._app.DEFAULT_RUNTIME_APPROVALS.exists() is False


# --- print-final-runbook read-only ---
def test_print_final_runbook_read_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc, out = _run(["print-final-runbook"])
    assert rc == 0 and PHRASE in out and INSTALL in out and "one-shot-live" in out
    assert list(tmp_path.iterdir()) == []


# --- no repo runtime/approvals created by any read/prepare path ---
def test_no_repo_runtime_approvals(tmp_path):
    _run(["status"], env={}, runner=FakeRunner(stdout="PASS"))
    _run(_prep_args(tmp_path / "pack"))
    assert fc._app.DEFAULT_RUNTIME_APPROVALS.exists() is False
