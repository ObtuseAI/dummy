from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from predator_mesh import staged_gate_common as sgc

_MOD_PATH = Path(sgc.ROOT) / "tools" / "operator_authority_appliance" / "operator_authority_appliance.py"
_spec = importlib.util.spec_from_file_location("operator_authority_appliance", _MOD_PATH)
app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app)

PHRASE = app.REQUIRED_PHRASE
RISK = app.REQUIRED_ACKNOWLEDGE_RISK
GOOD_ENV = {"DUMMY_LIVE_PROOF_MODE": "1", "DUMMY_LIVE_PROOF_ACK": "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"}


@pytest.fixture(autouse=True)
def _patch_runtime_approvals(tmp_path, monkeypatch):
    """Keep tests isolated from any real runtime/approvals installed in the repo."""
    monkeypatch.setattr(app, "DEFAULT_RUNTIME_APPROVALS", tmp_path / "runtime" / "approvals")


def _build(out: Path, **over):
    kw = dict(output_dir=out, operator="chris", reason="controlled pilot", expires_at="2026-07-07T21:00:00Z",
              proof_target="FIRST_REAL_PILOT_PROOF", typed_approval=PHRASE, acknowledge_risk=RISK)
    kw.update(over)
    return app.build_authority_pack(**kw)


class Recorder:
    def __init__(self):
        self.cmds = []

    def __call__(self, cmd):
        self.cmds.append(" ".join(cmd))
        return {"cmd": " ".join(cmd), "returncode": 0, "stdout": "", "stderr": ""}


# --- status is read-only ---
def test_status_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DEFAULT_RUNTIME_APPROVALS", tmp_path / "runtime" / "approvals")
    s = app.status()
    assert s["proof_starvation_stop_rule_active"] is True
    assert (tmp_path / "runtime" / "approvals").exists() is False


# --- init-templates writes only under templates dir ---
def test_init_templates_writes_only_templates(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "TEMPLATES_DIR", tmp_path / "templates")
    written = app.init_templates()
    assert written and all(str(tmp_path / "templates") in w for w in written)
    for w in written:
        assert "NOT_APPROVAL" in Path(w).read_text(encoding="utf-8")


# --- build rejects missing / fuzzy / broad / market / scale approvals ---
def test_build_rejects_missing_approval(tmp_path):
    r = _build(tmp_path / "o", typed_approval="")
    assert r["ok"] is False and "APPROVAL_PHRASE_NOT_EXACT" in r["errors"] and r["written"] == []


def test_build_rejects_fuzzy_approval(tmp_path):
    r = _build(tmp_path / "o", typed_approval="I approve Dummy to run a pilot")
    assert r["ok"] is False and "APPROVAL_PHRASE_NOT_EXACT" in r["errors"]


def test_build_rejects_broad_approval(tmp_path):
    r = _build(tmp_path / "o", reason="grant full live trading across all markets")
    assert r["ok"] is False and "BROAD_APPROVAL_REJECTED" in r["errors"]


def test_build_rejects_market_order_approval(tmp_path):
    r = _build(tmp_path / "o", acknowledge_risk=RISK + " and allow market order")
    assert r["ok"] is False and "MARKET_ORDER_APPROVAL_REJECTED" in r["errors"]


def test_build_rejects_scale_autonomy_approval(tmp_path):
    r = _build(tmp_path / "o", reason="controlled pilot and enable scale")
    assert r["ok"] is False and "SCALE_OR_AUTONOMY_APPROVAL_REJECTED" in r["errors"]


def test_build_rejects_missing_operator_reason_expiry(tmp_path):
    r = _build(tmp_path / "o", operator="", reason="", expires_at="")
    assert r["ok"] is False
    assert {"MISSING_OPERATOR", "MISSING_REASON", "MISSING_EXPIRY"} <= set(r["errors"])


# --- build accepts exact phrase into operator-owned output dir ---
def test_build_accepts_exact_phrase(tmp_path):
    out = tmp_path / "operator_owned"
    r = _build(out)
    assert r["ok"] is True and r["errors"] == []
    for name in app.PACK_FILES:
        assert (out / name).exists()
    approval = app._load_json(out / app.APPROVAL_FILENAME)
    assert approval["exact_phrase"] == PHRASE
    assert app._load_json(out / "authority_manifest.json")["not_self_authorized_by_dummy"] is True


# --- verify passes exact pack, fails on tamper ---
def test_verify_passes_exact_pack(tmp_path):
    out = tmp_path / "o"
    _build(out)
    v = app.verify_authority_pack(out)
    assert v["ok"] is True
    assert v["checks"]["exact_approval_phrase"] and v["checks"]["hashes_match"]
    assert v["checks"]["no_market_order_permission"] and v["checks"]["no_scale_autonomy_permission"]


def test_verify_fails_modified_phrase(tmp_path):
    out = tmp_path / "o"
    _build(out)
    p = out / app.APPROVAL_FILENAME
    import json
    d = json.loads(p.read_text(encoding="utf-8")); d["exact_phrase"] = "tampered"
    p.write_text(json.dumps(d), encoding="utf-8")
    v = app.verify_authority_pack(out)
    assert v["ok"] is False and v["checks"]["exact_approval_phrase"] is False


# --- install: requires confirmation, writes only temp runtime ---
def test_install_requires_confirmation(tmp_path):
    out = tmp_path / "o"; _build(out)
    r = app.install_authority_pack(source_dir=out, operator_confirm_install="nope", runtime_approvals_dir=tmp_path / "rt")
    assert r["ok"] is False and r["error"] == "INSTALL_CONFIRMATION_NOT_EXACT"
    assert not (tmp_path / "rt").exists()


def test_install_writes_only_temp_runtime(tmp_path):
    out = tmp_path / "o"; _build(out)
    rt = tmp_path / "rt" / "approvals"
    r = app.install_authority_pack(source_dir=out, operator_confirm_install=app.INSTALL_CONFIRM_PHRASE, runtime_approvals_dir=rt)
    assert r["ok"] is True
    assert (rt / app.APPROVAL_FILENAME).exists()
    assert r["live_submit_modified"] is False and r["caps_modified"] is False and r["adapter_injected_by_appliance"] is False
    # Real repo runtime/approvals never touched.
    assert not (app.DEFAULT_RUNTIME_APPROVALS / app.APPROVAL_FILENAME).exists()


# --- dry-run-all and run-authority-checks never call execute-once ---
def test_dry_run_all_no_execute_once():
    rec = Recorder()
    r = app.dry_run_all(runner=rec)
    assert r["execute_once_called"] is False
    assert not any("execute_once_final_proof_v7" in c for c in rec.cmds)


def test_run_authority_checks_no_execute_once():
    rec = Recorder()
    r = app.run_authority_checks(runner=rec)
    assert r["execute_once_called"] is False
    assert not any("execute_once_final_proof_v7" in c for c in rec.cmds)


# --- run-live-proof-once blocks without env gate / seal / proof lock ---
def test_run_live_proof_once_blocks_without_env_gate():
    rec = Recorder()
    r = app.run_live_proof_once(runner=rec, env={}, seal_status="PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT", proof_lock=False)
    assert r["verdict"] == "BLOCKED_ENV_GATE_ABSENT" and r["execute_once_called"] is False
    assert rec.cmds == []


def test_run_live_proof_once_blocks_without_command_seal():
    rec = Recorder()
    r = app.run_live_proof_once(runner=rec, env=GOOD_ENV, seal_status="PARTIAL_COMMAND_SEAL_BLOCKED_AUTHORITY_ABSENT", proof_lock=False)
    assert r["verdict"] == "BLOCKED_COMMAND_SEAL_NOT_READY" and r["execute_once_called"] is False
    assert rec.cmds == []


def test_run_live_proof_once_blocks_if_proof_lock_used():
    rec = Recorder()
    r = app.run_live_proof_once(runner=rec, env=GOOD_ENV, seal_status="PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT", proof_lock=True)
    assert r["verdict"] == "BLOCKED_PROOF_LOCK_ALREADY_USED" and r["execute_once_called"] is False
    assert rec.cmds == []


# --- Dummy is never self-authorized: appliance default status shows locked/no-runtime ---
def test_appliance_never_self_authorizes_dummy():
    s = app.status()
    assert "NOT executable authority" in s["note"]
    # No repo runtime/approvals created merely by reading status.
    assert app.DEFAULT_RUNTIME_APPROVALS.exists() is False
