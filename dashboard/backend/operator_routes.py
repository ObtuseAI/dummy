"""Operator control panel API — drives the EXISTING operator-side appliance only.

Every endpoint shells out to tools/operator_authority_appliance/operator_full_completion.py
(the same commands the operator would run in a terminal). No gate is bypassed:
the appliance still fails closed at the command seal. The live endpoint refuses
unless the caller submits the exact env-gate ack strings — the dashboard cannot
fire a real order on its own, exactly like the CLI.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/operator", tags=["operator"])

DUMMY_ROOT = Path(__file__).resolve().parents[2]
APPLIANCE = "tools/operator_authority_appliance/operator_full_completion.py"

# Exact phrases — must match the appliance / mission verbatim.
TYPED_APPROVAL = ("I approve Dummy to run one controlled production pilot through "
                  "LiveBrokerFirewall only, with no market orders, strict caps, "
                  "live-submit already operator-enabled, per-order fail-closed checks, "
                  "and immediate pilot auto-lock")
RISK_ACK = ("I understand this can place one real limit order only through "
            "LiveBrokerFirewall after all Dummy gates pass")
INSTALL_CONFIRM = "I authorize installing these operator-created authority files into Dummy runtime"
ENV_MODE = ("DUMMY_LIVE_PROOF_MODE", "1")
ENV_ACK = ("DUMMY_LIVE_PROOF_ACK", "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY")


def _run(args: list[str], extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, APPLIANCE, *args],
        cwd=str(DUMMY_ROOT), capture_output=True, text=True, env=env,
    )
    return {
        "cmd": " ".join(["operator_full_completion.py", *args]),
        "returncode": proc.returncode,
        "stdout": proc.stdout[-6000:],
        "stderr": proc.stderr[-2000:],
    }


def _live_submit_state() -> dict[str, Any]:
    import json
    p = DUMMY_ROOT / "configs" / "live_submit.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": False, "note": "config absent"}


@router.get("/status")
async def operator_status() -> dict[str, Any]:
    result = _run(["status"])
    return {**result, "live_submit_config": _live_submit_state()}


@router.post("/prepare")
async def operator_prepare() -> dict[str, Any]:
    return _run([
        "one-shot-prepare",
        "--operator", "chris",
        "--reason", "controlled pilot",
        "--expires-at", "2026-07-08T21:00:00Z",
        "--authority-pack-dir", "operator_authority_pack",
        "--typed-approval", TYPED_APPROVAL,
        "--risk-ack", RISK_ACK,
    ])


@router.post("/install")
async def operator_install() -> dict[str, Any]:
    return _run([
        "one-shot-install",
        "--authority-pack-dir", "operator_authority_pack",
        "--operator-confirm-install", INSTALL_CONFIRM,
    ], extra_env={
        "DUMMY_AUTHORITY_INSTALL_CONFIRM": INSTALL_CONFIRM,
        "DUMMY_AUTHORITY_PACK_DIR": "operator_authority_pack",
        "DUMMY_OPERATOR_NAME": "chris",
        "DUMMY_OPERATOR_REASON": "controlled pilot",
        "DUMMY_OPERATOR_EXPIRES_AT": "2026-07-08T21:00:00Z",
        "DUMMY_TYPED_APPROVAL": TYPED_APPROVAL,
        "DUMMY_RISK_ACK": RISK_ACK,
    })


@router.post("/check")
async def operator_check() -> dict[str, Any]:
    return _run(["one-shot-check"])


class LiveBody(BaseModel):
    mode_ack: str = ""   # must equal ENV_MODE[1]
    proof_ack: str = ""  # must equal ENV_ACK[1]


@router.post("/live")
async def operator_live(body: LiveBody) -> dict[str, Any]:
    """Runs one-shot-live. Refuses unless the caller supplies the exact env-gate
    acks. Even armed, the appliance fails closed at the command seal — this
    cannot manufacture a real order. It is the same command the operator would
    run by hand, no more permissive."""
    if body.mode_ack != ENV_MODE[1] or body.proof_ack != ENV_ACK[1]:
        return {
            "refused": True,
            "reason": "ENV_GATE_ACK_MISMATCH",
            "required": {ENV_MODE[0]: ENV_MODE[1], ENV_ACK[0]: ENV_ACK[1]},
            "hint": "Type the exact ack strings to arm the env gate. This does not bypass the command seal.",
        }
    result = _run(["one-shot-live"], extra_env={ENV_MODE[0]: ENV_MODE[1], ENV_ACK[0]: ENV_ACK[1]})
    return {"refused": False, **result}
