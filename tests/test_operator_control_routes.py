"""Focused tests for the operator-control API backend wrapper.

We mock subprocess.run so NO real CLI is invoked, NO broker is contacted,
and NO live proof can fire. Tests assert the safety invariants:
  * shell=False always
  * one-shot-live fails closed on any mismatched confirmation
  * one-shot-live only calls operator_full_completion.py one-shot-live when armed
  * env gate vars are scoped to that subprocess only
  * no market/scale/autonomy flags
  * dry-run never calls execute-once
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

# Load the route module directly (avoid importing the whole FastAPI app, which
# pulls in many heavy deps unrelated to these safety checks).
MOD_PATH = (
    Path(__file__).resolve().parents[1]
    / "dashboard" / "backend" / "operator_control_routes.py"
)
_spec = importlib.util.spec_from_file_location("operator_control_routes", MOD_PATH)
ocr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ocr)


class FakeProc:
    def __init__(self, returncode=0, stdout="ok", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run_kwargs(call_args, call_kwargs):
    return call_args, call_kwargs


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_runs_readonly_commands_and_shell_false():
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return FakeProc(0, stdout="command seal: BLOCKED\nlive-submit: disabled", stderr="")

    with mock.patch.object(ocr.subprocess, "run", side_effect=fake_run):
        res = await ocr.status()

    assert res["live_orders"] == 0
    assert res["broker_contact"] is False
    assert res["market_order"] is False
    assert res["scale"] is False
    assert res["autonomy"] is False
    assert res["runtime_approvals_mutated"] is False
    assert res["caps_mutated"] is False
    assert res["live_submit_mutated"] is False
    assert res["route_proof_state"]["mentions_command_seal"] is True
    # three readonly commands ran
    scripts = [c[0][1] for c in calls]
    assert any("operator_full_completion.py" in s for s in scripts)
    assert any("run_dummy_proof_starvation_stop_rule.py" in s for s in scripts)
    # shell=False everywhere
    assert all(c[1].get("shell") is False for c in calls)
    assert all("cwd" in c[1] for c in calls)


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_calls_authority_appliance_dry_run_all_not_execute_once():
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return FakeProc(0, stdout="dry-run ok", stderr="")

    with mock.patch.object(ocr.subprocess, "run", side_effect=fake_run):
        res = await ocr.dry_run()

    assert res["ok"] is True
    cmd = calls[0][0]
    assert "operator_authority_appliance.py" in cmd[1]
    assert "dry-run-all" in cmd
    assert "execute-once" not in cmd
    assert "run-live-proof-once" not in cmd
    assert calls[0][1]["shell"] is False


# ---------------------------------------------------------------------------
# max-progress
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_progress_uses_bootstrap_and_no_danger_flags():
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return FakeProc(0, stdout="max-progress ok", stderr="")

    with mock.patch.object(ocr.subprocess, "run", side_effect=fake_run):
        res = await ocr.max_progress()

    cmd = calls[0][0]
    assert "operator_bootstrap.py" in cmd[1]
    assert "max-progress" in cmd
    joined = " ".join(cmd)
    assert "--market" not in joined
    assert "--scale" not in joined
    assert "--autonomy" not in joined
    assert "--enable-live-submit" not in joined
    assert calls[0][1]["shell"] is False


# ---------------------------------------------------------------------------
# one-shot-check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_shot_check_only_runs_check():
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return FakeProc(0, stdout="check ok", stderr="")

    with mock.patch.object(ocr.subprocess, "run", side_effect=fake_run):
        await ocr.one_shot_check()

    cmd = calls[0][0]
    assert "operator_full_completion.py" in cmd[1]
    assert "one-shot-check" in cmd
    assert "one-shot-live" not in " ".join(cmd)


# ---------------------------------------------------------------------------
# one-shot-live — fail closed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_shot_live_rejects_missing_mode_ack():
    body = ocr.OneShotLiveBody(live_proof_mode="", live_proof_ack=ocr.ENV_ACK_VAL,
                               typed_confirm=ocr.TYPED_CONFIRM_SENTENCE)
    with mock.patch.object(ocr.subprocess, "run") as run:
        res = await ocr.one_shot_live(body)
    assert res["refused"] is True
    assert res["ok"] is False
    run.assert_not_called()


@pytest.mark.asyncio
async def test_one_shot_live_rejects_missing_proof_ack():
    body = ocr.OneShotLiveBody(live_proof_mode="1", live_proof_ack="",
                               typed_confirm=ocr.TYPED_CONFIRM_SENTENCE)
    with mock.patch.object(ocr.subprocess, "run") as run:
        res = await ocr.one_shot_live(body)
    assert res["refused"] is True
    run.assert_not_called()


@pytest.mark.asyncio
async def test_one_shot_live_rejects_mismatched_typed_confirm():
    body = ocr.OneShotLiveBody(live_proof_mode="1", live_proof_ack=ocr.ENV_ACK_VAL,
                               typed_confirm="i think this is fine")
    with mock.patch.object(ocr.subprocess, "run") as run:
        res = await ocr.one_shot_live(body)
    assert res["refused"] is True
    assert res["reason"] == "TYPED_CONFIRM_MISMATCH"
    run.assert_not_called()


@pytest.mark.asyncio
async def test_one_shot_live_rejects_wrong_mode_value():
    body = ocr.OneShotLiveBody(live_proof_mode="2", live_proof_ack=ocr.ENV_ACK_VAL,
                               typed_confirm=ocr.TYPED_CONFIRM_SENTENCE)
    with mock.patch.object(ocr.subprocess, "run") as run:
        res = await ocr.one_shot_live(body)
    assert res["refused"] is True
    assert res["reason"] == "LIVE_PROOF_MODE_MISMATCH"
    run.assert_not_called()


# ---------------------------------------------------------------------------
# one-shot-live — armed path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_shot_live_armed_calls_only_one_shot_live_with_scoped_env():
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return FakeProc(0, stdout="live proof ok", stderr="")

    with mock.patch.object(ocr.subprocess, "run", side_effect=fake_run):
        body = ocr.OneShotLiveBody(live_proof_mode="1", live_proof_ack=ocr.ENV_ACK_VAL,
                                   typed_confirm=ocr.TYPED_CONFIRM_SENTENCE)
        res = await ocr.one_shot_live(body)

    assert res.get("refused") in (False, None)  # not refused
    assert res["ok"] is True
    cmd = calls[0][0]
    assert "operator_full_completion.py" in cmd[1]
    assert "one-shot-live" in cmd
    joined = " ".join(cmd)
    # must never call execute-once / broker adapters directly
    assert "execute-once" not in joined
    assert "--market" not in joined
    assert "--scale" not in joined
    assert "--autonomy" not in joined
    assert "--enable-live-submit" not in joined
    # shell=False
    assert calls[0][1]["shell"] is False
    # env gate vars passed to that subprocess only
    env = calls[0][1]["env"]
    assert env[ocr.ENV_MODE_KEY] == "1"
    assert env[ocr.ENV_ACK_KEY] == ocr.ENV_ACK_VAL
    # cwd pinned to repo root
    assert calls[0][1]["cwd"] == str(ocr.DUMMY_ROOT)


# ---------------------------------------------------------------------------
# _result structure
# ---------------------------------------------------------------------------

def test_result_structure_has_required_fields():
    r = ocr._result(["x"], label="lbl", returncode=0, stdout="s", stderr="",
                    safety_notes=["a"])
    for key in ("ok", "command", "returncode", "stdout", "stderr", "safety_notes"):
        assert key in r
    assert r["ok"] is True
    assert r["command"] == "lbl"
    assert r["safety_notes"] == ["a"]
