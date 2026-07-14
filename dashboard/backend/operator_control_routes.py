"""Operator-control API for the local dashboard launcher.

This is a thin wrapper around the EXISTING operator-side CLI tools. It never
implements trading logic, never bypasses the command seal / resolver /
LiveBrokerFirewall, and never contacts the broker on its own. Every endpoint
just shells out to the same scripts the operator would run by hand and returns
structured JSON.

Safety invariants enforced here:
  * subprocess.run(shell=False) always.
  * cwd pinned to the repo root.
  * stdout/stderr captured and tail-trimmed (no secret redaction needed here
    because no credentials are ever injected; the appliance handles its own
    secret hygiene).
  * The only "danger" endpoint is one-shot-live, and it fails closed unless the
    caller supplies the exact env-gate acks AND the exact typed risk sentence.
    Even armed, it can only invoke `operator_full_completion.py one-shot-live`;
    it never calls execute-once / broker adapters / market orders directly.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from core.live_submit_state import (
    LIVE_SUBMIT_REQUIRED_ACK,
    LIVE_SUBMIT_TYPED_CONFIRMATION,
    validate_operator_one_proof_enabled,
)
from core import proof_lock
from core.proof_authority import REQUIRED_CONFIRMATION as SECOND_PROOF_REQUIRED_CONFIRMATION

router = APIRouter(prefix="/api/operator-control", tags=["operator-control"])

DUMMY_ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable

NEXT_PROOF_CANDIDATE_DIR = DUMMY_ROOT / "artifacts" / "dummy" / "next_proof_candidate"
V1_CANDIDATE_PATH = NEXT_PROOF_CANDIDATE_DIR / "VALIDATED_KALSHI_PROOF_CANDIDATE.json"
V2_CANDIDATE_PATH = NEXT_PROOF_CANDIDATE_DIR / "VALIDATED_KALSHI_PROOF_CANDIDATE_V2.json"
V2_REPORT_PATH = NEXT_PROOF_CANDIDATE_DIR / "NEXT_PROOF_CANDIDATE_READ_ONLY_METADATA_REPORT.json"
V3_CANDIDATE_PATH = NEXT_PROOF_CANDIDATE_DIR / "VALIDATED_KALSHI_PROOF_CANDIDATE_V3.json"
V3_REPORT_PATH = NEXT_PROOF_CANDIDATE_DIR / "NEXT_PROOF_CANDIDATE_DISCOVERY_V3_REPORT.json"

FULL_COMPLETION = "tools/operator_authority_appliance/operator_full_completion.py"
AUTHORITY_APPLIANCE = "tools/operator_authority_appliance/operator_authority_appliance.py"
BOOTSTRAP = "tools/operator_authority_appliance/operator_bootstrap.py"
STARVATION_STOP = "scripts/run_dummy_proof_starvation_stop_rule.py"

# Exact env-gate ack strings — must match the appliance / mission verbatim.
ENV_MODE_KEY = "DUMMY_LIVE_PROOF_MODE"
ENV_MODE_VAL = "1"
ENV_ACK_KEY = "DUMMY_LIVE_PROOF_ACK"
ENV_ACK_VAL = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
TYPED_CONFIRM_SENTENCE = (
    "I understand this can place one real limit order only through "
    "LiveBrokerFirewall after all Dummy gates pass"
)

DEFAULT_TIMEOUT = 120


def _result(
    args: list[str],
    *,
    label: str,
    returncode: int,
    stdout: str,
    stderr: str,
    safety_notes: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ok": returncode == 0,
        "command": label,
        "returncode": returncode,
        "stdout": stdout[-8000:],
        "stderr": stderr[-3000:],
        "safety_notes": safety_notes or [],
    }
    if extra:
        out.update(extra)
    return out


def _run_script(
    script: str,
    args: list[str],
    *,
    extra_env: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    safety_notes: list[str] | None = None,
) -> dict[str, Any]:
    """Run a repo-relative python script with shell=False, cwd=repo root."""
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    cmd = [PY, script, *args]
    label = " ".join([Path(script).name, *args])
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(DUMMY_ROOT),
            capture_output=True,
            text=True,
            env=env,
            shell=False,
            timeout=timeout,
        )
        return _result(
            args,
            label=label,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            safety_notes=safety_notes,
        )
    except subprocess.TimeoutExpired as e:
        return _result(
            args,
            label=label,
            returncode=-1,
            stdout=e.stdout or "" if isinstance(e.stdout, str) else "",
            stderr=f"[TIMEOUT after {timeout}s] {e.stderr or ''}",
            safety_notes=(safety_notes or []) + ["timeout-reached"],
        )
    except Exception as e:  # pragma: no cover - defensive
        return _result(
            args,
            label=label,
            returncode=-1,
            stdout="",
            stderr=f"[runner-error] {type(e).__name__}: {e}",
            safety_notes=(safety_notes or []) + ["runner-error"],
        )


def _live_submit_state() -> dict[str, Any]:
    import json
    p = DUMMY_ROOT / "configs" / "live_submit.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": False, "note": "config absent"}


REAL_PROOF_REGISTRY_PATH = DUMMY_ROOT / "artifacts" / "dummy" / "real_proof_registry.json"


def _load_real_proof_registry() -> dict[str, Any] | None:
    """Read the preserved real-proof registry safely; return None if missing/invalid."""
    if not REAL_PROOF_REGISTRY_PATH.exists():
        return None
    try:
        data = json.loads(REAL_PROOF_REGISTRY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _approvals_state() -> dict[str, Any]:
    p = DUMMY_ROOT / "runtime" / "approvals"
    files: list[str] = []
    if p.exists():
        try:
            files = sorted(f.name for f in p.iterdir() if f.is_file())
        except Exception:
            files = []
    return {"path": str(p), "files": files, "count": len(files)}


def _parse_status_stdout(stdout: str) -> dict[str, Any]:
    """Best-effort parse of operator_full_completion status output."""
    text = stdout.lower()
    return {
        "mentions_command_seal": "command seal" in text,
        "mentions_blocked": "blocked" in text,
        "mentions_armable": "armable" in text or "armed" in text,
        "mentions_live_submit": "live-submit" in text or "live_submit" in text,
    }


@router.get("/status")
async def status() -> dict[str, Any]:
    """Read-only: runs status, doctor, and the proof-starvation stop rule."""
    safety = [
        "read-only",
        "no broker contact",
        "no order placement",
        "shell=False",
    ]
    status_r = _run_script(FULL_COMPLETION, ["status"], safety_notes=safety)
    doctor_r = _run_script(FULL_COMPLETION, ["doctor"], safety_notes=safety)
    starvation_r = _run_script(STARVATION_STOP, [], safety_notes=safety)

    live_submit = _live_submit_state()
    approvals = _approvals_state()
    parsed = _parse_status_stdout(status_r.get("stdout", ""))

    # Completion percent heuristic from status stdout: look for "X%" or
    # "complete" markers. Conservative — never claims 100%.
    pct = None
    import re
    m = re.search(r"(\d{1,3})\s*%", status_r.get("stdout", ""))
    if m:
        pct = min(99, int(m.group(1)))

    registry = _load_real_proof_registry()
    if registry and registry.get("latest_real_broker_contacted") is True:
        proof_lock_status = "consumed_by_real_broker_attempt"
    elif registry:
        proof_lock_status = "registry_present_no_broker_contact"
    else:
        proof_lock_status = "no_registry"

    preserved_real_proof: dict[str, Any] = {
        "latest_real_broker_proof_attempt_status": registry.get("latest_real_broker_attempt_status") if registry else None,
        "broker_contacted": bool(registry.get("latest_real_broker_contacted")) if registry else False,
        "live_order_accepted": False,
        "evidence_directory": registry.get("latest_real_broker_proof_evidence_dir") if registry else None,
        "current_live_submit_disabled_default": bool(live_submit.get("enabled")) is False,
        "proof_lock_status": proof_lock_status,
        "next_action_recommendation": "investigate broker rejection/order payload validity",
    }

    return {
        "ok": status_r["ok"] and doctor_r["ok"],
        "live_orders": 0,
        "broker_contact": False,
        "market_order": False,
        "scale": False,
        "autonomy": False,
        "live_submit_config": live_submit,
        "approvals": approvals,
        "runtime_approvals_mutated": False,
        "caps_mutated": False,
        "live_submit_mutated": False,
        "command_seal_mentioned": parsed["mentions_command_seal"],
        "route_proof_state": parsed,
        "completion_percent": pct,
        "preserved_real_proof": preserved_real_proof,
        "safety_notes": safety,
        "results": {
            "status": status_r,
            "doctor": doctor_r,
            "proof_starvation_stop": starvation_r,
        },
    }


def _load_v1_status() -> dict[str, Any] | None:
    """Read the V1 candidate packet and return a secret-free status, or None."""
    data = _read_json(V1_CANDIDATE_PATH)
    if not isinstance(data, dict):
        return None

    market_checks = data.get("market_metadata_checks") or {}
    contract_checks = data.get("contract_metadata_checks") or {}
    if not isinstance(market_checks, dict):
        market_checks = {}
    if not isinstance(contract_checks, dict):
        contract_checks = {}

    return {
        "candidate_validation_status": "validated_schema_only",
        "market_validated": bool(market_checks.get("valid", False)),
        "contract_validated": bool(contract_checks.get("valid", False)),
        "read_only_metadata_mode": str(data.get("metadata_mode", "none")),
        "submit_allowed_now": bool(data.get("submit_allowed_now", False)),
        "requires_new_operator_proof_authority": bool(data.get("requires_new_operator_proof_authority", True)),
        "reason_submit_not_allowed": str(data.get("reason_submit_not_allowed", "unknown")),
        "proof_lock_status": str(data.get("proof_lock_status", "unknown")),
        "next_action": "review candidate packet and create new explicit operator proof authority",
        "secrets_redacted": True,
    }


def _fallback_v1_status() -> dict[str, Any]:
    """Safe fallback when no V1 artifact has been generated yet."""
    proof_lock_consumed = proof_lock.real_proof_attempt_exists()
    if proof_lock_consumed:
        proof_lock_status = "consumed_by_real_broker_attempt"
        reason = "previous real broker attempt recorded; new operator proof authority required"
    else:
        proof_lock_status = "clear"
        reason = "live-submit disabled by default; explicit operator authority required"

    return {
        "candidate_validation_status": "validated_schema_only",
        "market_validated": False,
        "contract_validated": False,
        "read_only_metadata_mode": "none",
        "submit_allowed_now": False,
        "requires_new_operator_proof_authority": True,
        "reason_submit_not_allowed": reason,
        "proof_lock_status": proof_lock_status,
        "next_action": "review candidate packet and create new explicit operator proof authority",
        "secrets_redacted": True,
    }


def _load_v2_status() -> dict[str, Any]:
    """Read the V2 candidate packet/report and return a secret-free status."""
    data = _read_json(V2_CANDIDATE_PATH)
    report = _read_json(V2_REPORT_PATH)

    if not isinstance(data, dict) and not isinstance(report, dict):
        return {
            "status": "not_generated_yet",
            "candidate_found": False,
            "submit_allowed_now": False,
            "requires_new_operator_proof_authority": True,
            "proof_lock_status": "consumed_by_real_broker_attempt",
            "next_action": "review candidate; create new proof authority only if operator accepts",
            "no_submit_button": True,
            "no_live_submit_auto_enable": True,
            "secrets_redacted": True,
        }

    if not isinstance(data, dict):
        data = {}
    if not isinstance(report, dict):
        report = {}

    return {
        "candidate_found": bool(data.get("candidate_found", False)),
        "market_ticker": data.get("market_ticker"),
        "contract_ticker": data.get("contract_ticker"),
        "market_tradable": bool(data.get("market_tradable", False)),
        "contract_tradable": bool(data.get("contract_tradable", False)),
        "price_validated": bool(data.get("price_validated", False)),
        "submit_allowed_now": False,
        "requires_new_operator_proof_authority": True,
        "proof_lock_status": "consumed_by_real_broker_attempt",
        "next_action": "review candidate; create new proof authority only if operator accepts",
        "no_submit_button": True,
        "no_live_submit_auto_enable": True,
        "secrets_redacted": True,
        "read_only_metadata_contact": bool(
            data.get("read_only_metadata_contact")
            or report.get("read_only_metadata_contact")
            or False
        ),
        "price_source": str(
            data.get("price_source") or report.get("price_source") or "unknown"
        ),
        "price": data.get("price") if data.get("price") is not None else report.get("price"),
    }


def _load_v3_status() -> dict[str, Any]:
    """Read the V3 discovery candidate packet/report and return a secret-free status."""
    data = _read_json(V3_CANDIDATE_PATH)
    report = _read_json(V3_REPORT_PATH)

    if not isinstance(data, dict) and not isinstance(report, dict):
        return {
            "status": "not_generated_yet",
            "candidate_found": False,
            "submit_allowed_now": False,
            "requires_new_operator_proof_authority": True,
            "proof_lock_status": "consumed_by_real_broker_attempt",
            "next_action": "run read-only discovery to produce V3 candidate",
            "no_submit_button": True,
            "no_live_submit_auto_enable": True,
            "secrets_redacted": True,
        }

    if not isinstance(data, dict):
        data = {}
    if not isinstance(report, dict):
        report = {}

    return {
        "status": str(report.get("verdict") or data.get("validation_mode") or "unknown"),
        "discovery_mode": str(data.get("discovery_mode") or report.get("discovery_mode") or "unknown"),
        "candidate_found": bool(data.get("candidate_found", False)),
        "market_ticker": data.get("market_ticker") or report.get("market_ticker"),
        "contract_ticker": data.get("contract_ticker") or report.get("contract_ticker"),
        "market_status": data.get("market_status") or report.get("market_status"),
        "contract_status": data.get("contract_status") or report.get("contract_status"),
        "market_tradable": bool(data.get("market_tradable", False)),
        "contract_tradable": bool(data.get("contract_tradable", False)),
        "price_validated": bool(data.get("price_validated", False)),
        "price_source": str(data.get("price_source") or report.get("price_source") or "unknown"),
        "price": data.get("price") if data.get("price") is not None else report.get("price"),
        "read_only_metadata_contact": bool(
            data.get("read_only_metadata_contact")
            or report.get("read_only_metadata_contact")
            or False
        ),
        "get_request_count": int(data.get("get_request_count") or report.get("get_request_count") or 0),
        "write_request_count": int(data.get("write_request_count") or report.get("write_request_count") or 0),
        "blocked_write_request_count": int(
            data.get("blocked_write_request_count") or report.get("blocked_write_request_count") or 0
        ),
        "response_schema_summary": str(
            data.get("response_schema_summary") or report.get("response_schema_summary") or "unknown"
        ),
        "candidate_selection_trace": list(
            data.get("candidate_selection_trace") or report.get("candidate_selection_trace") or []
        ),
        "exact_blockers": list(data.get("exact_blockers") or report.get("exact_blockers") or []),
        "submit_allowed_now": False,
        "requires_new_operator_proof_authority": True,
        "proof_lock_status": "consumed_by_real_broker_attempt",
        "next_action": "review V3 candidate; create new proof authority only if operator accepts",
        "no_submit_button": True,
        "no_live_submit_auto_enable": True,
        "secrets_redacted": True,
    }


SECOND_PROOF_DIR = DUMMY_ROOT / "artifacts" / "dummy" / "second_proof_authority"


def _load_second_proof_authority_status() -> dict[str, Any]:
    """Read-only second-proof authority status (draft/active/used/absent)."""
    draft_path = SECOND_PROOF_DIR / "SECOND_PROOF_AUTHORITY_DRAFT.json"
    active_path = SECOND_PROOF_DIR / "SECOND_PROOF_AUTHORITY_ACTIVE.json"
    preflight_path = SECOND_PROOF_DIR / "SECOND_PROOF_PREFLIGHT_REPORT.json"

    state = "absent"
    authority_data: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None

    if active_path.exists():
        state = "active"
        authority_data = _read_json(active_path)
    elif draft_path.exists():
        state = "draft"
        authority_data = _read_json(draft_path)

    if preflight_path.exists():
        preflight = _read_json(preflight_path)

    return {
        "state": state,
        "authority_id": authority_data.get("authority_id") if authority_data else None,
        "candidate_market_ticker": authority_data.get("candidate_market_ticker") if authority_data else None,
        "candidate_contract_ticker": authority_data.get("candidate_contract_ticker") if authority_data else None,
        "candidate_price": authority_data.get("candidate_price") if authority_data else None,
        "candidate_count": authority_data.get("candidate_count") if authority_data else None,
        "candidate_order_type": authority_data.get("candidate_order_type") if authority_data else None,
        "status": authority_data.get("status") if authority_data else None,
        "submit_allowed_now": False,
        "no_auto_live": True,
        "next_action": (
            "activate authority with exact typed confirmation, then arm env gate"
            if state == "draft"
            else "arm env gate and run one-shot-live once"
            if state == "active"
            else "run prepare-second-proof-authority to create draft"
        ),
        "preflight": preflight,
        "secrets_redacted": True,
    }


@router.get("/next-proof-candidate")
async def next_proof_candidate_status() -> dict[str, Any]:
    """Read-only next-proof candidate status (V1 + V2 + V3)."""
    v1_status = _load_v1_status() or _fallback_v1_status()
    v2_status = _load_v2_status()
    v3_status = _load_v3_status()

    # Keep the original V1 fields at the top level for backward compatibility,
    # and also expose the explicit v1/v2/v3 split for the panel.
    return {
        **v1_status,
        "v1_status": v1_status,
        "v2_status": v2_status,
        "v3_status": v3_status,
    }


@router.get("/second-proof-authority")
async def second_proof_authority_status() -> dict[str, Any]:
    """Read-only second-proof authority status."""
    return _load_second_proof_authority_status()


@router.post("/second-proof-authority/prepare")
async def second_proof_authority_prepare() -> dict[str, Any]:
    """Create a draft second-proof authority from the validated V3 candidate.

    Does not activate, does not enable live-submit, does not contact the broker,
    and does not consume any proof lock.
    """
    safety = [
        "draft-only",
        "no activation",
        "no live-submit enablement",
        "no broker contact",
        "no order placement",
        "shell=False",
    ]
    return _run_script(
        FULL_COMPLETION,
        ["prepare-second-proof-authority"],
        safety_notes=safety,
    )


class SecondProofAuthorityActivateBody(BaseModel):
    operator_name: str = ""
    reason: str = ""
    expires_at: str = ""
    confirm: str = ""


@router.post("/second-proof-authority/activate")
async def second_proof_authority_activate(body: SecondProofAuthorityActivateBody) -> dict[str, Any]:
    """Activate the draft second-proof authority after exact typed confirmation.

    Writes the active approval, creates a fresh second-proof lock namespace, and
    scopes live-submit.json to this authority. Does not run one-shot-live or
    contact the broker.
    """
    if body.confirm != SECOND_PROOF_REQUIRED_CONFIRMATION:
        return {
            "ok": False,
            "refused": True,
            "reason": "TYPED_CONFIRM_MISMATCH",
            "hint": "Type the exact second-proof confirmation sentence, character for character.",
            "safety_notes": [
                "activation blocked: confirmation mismatch",
                "no approval written",
                "no live-submit modified",
                "no broker contact",
                "no order placement",
            ],
        }

    safety = [
        "exact confirmation verified",
        "activates second-proof authority only",
        "no one-shot-live auto-run",
        "no broker contact",
        "no order placement",
        "shell=False",
    ]
    return _run_script(
        FULL_COMPLETION,
        [
            "activate-second-proof-authority",
            "--operator-name", body.operator_name,
            "--reason", body.reason,
            "--expires-at", body.expires_at,
            "--confirm", body.confirm,
        ],
        safety_notes=safety,
    )


@router.post("/dry-run")
async def dry_run() -> dict[str, Any]:
    safety = [
        "dry-run only",
        "no execute-once",
        "no broker contact",
        "no order placement",
        "shell=False",
    ]
    return _run_script(
        AUTHORITY_APPLIANCE,
        ["dry-run-all"],
        safety_notes=safety,
    )


@router.post("/max-progress")
async def max_progress() -> dict[str, Any]:
    """Runs `operator_bootstrap.py max-progress`. Fails closed by the CLI's own
    env-gate; this wrapper does not bypass it."""
    safety = [
        "fails closed at CLI env-gate",
        "no broker contact unless CLI gates arm",
        "no market/scale/autonomy flags injected",
        "shell=False",
    ]
    return _run_script(
        BOOTSTRAP,
        ["max-progress"],
        safety_notes=safety,
    )


@router.post("/one-shot-check")
async def one_shot_check() -> dict[str, Any]:
    safety = [
        "read-only check",
        "no broker contact",
        "no order placement",
        "shell=False",
    ]
    return _run_script(
        FULL_COMPLETION,
        ["one-shot-check"],
        safety_notes=safety,
    )


class OneShotLiveBody(BaseModel):
    live_proof_mode: str = ""
    live_proof_ack: str = ""
    typed_confirm: str = ""


def _live_refusal(reason: str, hint: str) -> dict[str, Any]:
    return {
        "ok": False,
        "refused": True,
        "reason": reason,
        "required": {
            ENV_MODE_KEY: ENV_MODE_VAL,
            ENV_ACK_KEY: ENV_ACK_VAL,
            "typed_confirm": TYPED_CONFIRM_SENTENCE,
        },
        "hint": hint,
        "returncode": 0,
        "stdout": "",
        "stderr": "",
        "safety_notes": [
            "refused: env-gate ack mismatch",
            "no subprocess invoked",
            "no broker contact",
            "no order placement",
        ],
    }


@router.post("/one-shot-live")
async def one_shot_live(body: OneShotLiveBody) -> dict[str, Any]:
    """The ONLY endpoint that can reach a real order path — and only by
    invoking `operator_full_completion.py one-shot-live`, exactly like the
    operator would type. Fails closed unless all three confirmations match
    verbatim. Even then, the appliance still fails closed at the command seal
    unless every real external system is in place."""
    if body.live_proof_mode != ENV_MODE_VAL:
        return _live_refusal(
            "LIVE_PROOF_MODE_MISMATCH",
            "Set DUMMY_LIVE_PROOF_MODE ack to exactly '1'.",
        )
    if body.live_proof_ack != ENV_ACK_VAL:
        return _live_refusal(
            "LIVE_PROOF_ACK_MISMATCH",
            f"Set DUMMY_LIVE_PROOF_ACK to exactly '{ENV_ACK_VAL}'.",
        )
    if body.typed_confirm != TYPED_CONFIRM_SENTENCE:
        return _live_refusal(
            "TYPED_CONFIRM_MISMATCH",
            "Type the risk acknowledgement sentence exactly, character for character.",
        )

    safety = [
        "env gate acks matched",
        "invokes operator_full_completion.py one-shot-live only",
        "no execute-once direct call",
        "no broker adapter injection",
        "no market/scale/autonomy flags",
        "appliance still fails closed at command seal",
        "shell=False",
        "env vars scoped to this subprocess only",
    ]
    return _run_script(
        FULL_COMPLETION,
        ["one-shot-live"],
        extra_env={
            ENV_MODE_KEY: ENV_MODE_VAL,
            ENV_ACK_KEY: ENV_ACK_VAL,
        },
        timeout=300,
        safety_notes=safety,
    )
# ---------------------------------------------------------------------------
# External prerequisites — operator-controlled, fail-closed workflows
# ---------------------------------------------------------------------------

# Paths for operator-staged external config.
OPERATOR_EXTERNAL_DIR = DUMMY_ROOT / "runtime" / "operator_external"
ADAPTER_DESCRIPTOR_PATH = OPERATOR_EXTERNAL_DIR / "livebrokerfirewall_adapter_descriptor.json"
LIVE_SUBMIT_PATH = DUMMY_ROOT / "configs" / "live_submit.json"
CAPS_PATH = DUMMY_ROOT / "configs" / "caps.json"
APPROVAL_PATH = (
    DUMMY_ROOT / "runtime" / "approvals" / "dummy_controlled_production_pilot_approval.json"
)

# Typed confirmation sentences.
ADAPTER_TYPED_CONFIRMATION = (
    "I confirm this is a real credentialed LiveBrokerFirewall adapter, not a stub, "
    "and it supports limit orders only"
)
CAPS_TYPED_CONFIRMATION = (
    "I confirm these caps are strict, limit-only, kill-switch protected, and for "
    "one controlled proof only"
)

# Strictness thresholds (cents). These match the smallest values already present
# in the established caps.json so the dashboard never broadens them.
STRICT_MAX_ORDER_SIZE_CENTS = 100
STRICT_MAX_DAILY_LOSS_CENTS = 500
STRICT_MAX_OPEN_EXPOSURE_CENTS = 1000

BANNED_ADAPTER_MARKERS = {"stub", "test", "dummy", "fixture"}
SECRET_KEYWORDS = {"api_key", "apikey", "api_secret", "secret", "private_key", "password", "token"}

ALLOWED_ADAPTER_MODULES = {
    "predator_mesh/brokers/kalshi_livebrokerfirewall_adapter.py",
    "adapters/live_broker_firewall_adapter_skeleton.py",
}
ALLOWED_ADAPTER_CLASS_NAMES = {"KalshiLiveBrokerFirewallAdapter", "LiveBrokerFirewallAdapter"}

KALSHI_KEY_ID_REFS = {"KALSHI_API_KEY_ID"}
KALSHI_PRIVATE_KEY_REFS = {
    "KALSHI_API_PRIVATE_KEY_PEM",
    "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    "KALSHI_PRIVATE_KEY",
    "KALSHI_PRIVATE_KEY_PATH",
}


class AdapterDescriptorBody(BaseModel):
    descriptor: dict[str, Any]
    typed_confirmation: str = ""


class AdapterRegisterBody(BaseModel):
    descriptor: dict[str, Any]
    operator_confirm_adapter_real: bool = False
    operator_confirm_not_stub: bool = False
    operator_confirm_limit_only: bool = False
    typed_confirmation: str


class LiveSubmitBody(BaseModel):
    enabled: bool = False
    operator: str = ""
    reason: str = ""
    expiry: str = ""
    proof_scope: str = "one_controlled_proof"
    typed_confirmation: str = ""


class CapsBody(BaseModel):
    max_order_count: int = 1
    max_order_size: int = STRICT_MAX_ORDER_SIZE_CENTS
    order_type_policy: str = "LIMIT_ONLY"
    market_orders_allowed: bool = False
    kill_switch_enabled: bool = True
    max_daily_loss: int = STRICT_MAX_DAILY_LOSS_CENTS
    max_open_exposure: int = STRICT_MAX_OPEN_EXPOSURE_CENTS
    operator: str = ""
    reason: str = ""
    expiry: str = ""
    typed_confirmation: str = ""


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON representation for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _sha256_canonical(obj: Any) -> str:
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _timestamp_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _backup_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + f".{_timestamp_suffix()}.bak")


def _atomic_write_json(path: Path, obj: Any) -> Path | None:
    """Write JSON atomically, returning the backup path if one was made."""
    path.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if path.exists():
        backup = _backup_path(path)
        path.replace(backup)
    canonical = _canonical_json(obj)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(canonical, encoding="utf-8")
    tmp.replace(path)
    return backup


def _safe_relative_path(value: str, root: Path) -> Path:
    """Resolve a relative path under root and reject traversal."""
    if not value:
        raise ValueError("empty path")
    candidate = (root / value).resolve()
    root_resolved = root.resolve()
    if not str(candidate).startswith(str(root_resolved) + os.sep) and candidate != root_resolved:
        raise ValueError("path traversal detected")
    return candidate


def _is_iso_timestamp(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def _looks_like_secret(value: str) -> bool:
    """Best-effort heuristic to catch inlined secrets."""
    if not isinstance(value, str):
        return False
    low = value.lower()
    # Long, space-less strings are likely keys/secrets.
    if len(value) > 64 and " " not in value:
        return True
    # Known secret prefixes.
    if any(value.startswith(p) for p in ("sk-", "AKIA", "ghp_", "glpat-")):
        return True
    # Keywords combined with length.
    if any(kw in low for kw in SECRET_KEYWORDS) and len(value) > 32:
        return True
    return False


def _has_stub_marker(value: str) -> bool:
    if not isinstance(value, str):
        return False
    low = value.lower()
    return any(marker in low for marker in BANNED_ADAPTER_MARKERS)


def _collect_credential_reference_names(data: dict[str, Any]) -> list[str]:
    """Return the union of single and list credential reference names."""
    refs: list[str] = []
    single = data.get("credential_reference_name")
    if isinstance(single, str) and single:
        refs.append(single)
    multi = data.get("credential_reference_names")
    if isinstance(multi, list):
        for item in multi:
            if isinstance(item, str):
                refs.append(item)
    return refs


def _validate_credential_reference_name(ref: Any, field: str) -> str | None:
    if not isinstance(ref, str) or not ref:
        return f"{field} must be a non-empty string"
    if _looks_like_secret(ref):
        return f"{field} appears to contain a raw secret; use a reference name only"
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", ref):
        return f"{field} must be an env-var-style reference (uppercase/underscore/digits)"
    return None


def _credential_reference_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    refs: list[str] = []

    single = data.get("credential_reference_name")
    if isinstance(single, str) and single:
        err = _validate_credential_reference_name(single, "credential_reference_name")
        if err:
            errors.append(err)
        else:
            refs.append(single)
    elif single is not None:
        errors.append("credential_reference_name must be a non-empty string")

    multi = data.get("credential_reference_names")
    if isinstance(multi, list):
        for i, item in enumerate(multi):
            err = _validate_credential_reference_name(item, f"credential_reference_names[{i}]")
            if err:
                errors.append(err)
            else:
                refs.append(item)
    elif multi is not None:
        errors.append("credential_reference_names must be a list of env-var-style references")

    if not refs:
        errors.append("at least one credential reference is required")
    elif data.get("broker") == "KALSHI":
        ref_set = set(refs)
        if not ref_set & KALSHI_KEY_ID_REFS:
            errors.append("Kalshi adapter requires credential reference KALSHI_API_KEY_ID")
        if not ref_set & KALSHI_PRIVATE_KEY_REFS:
            errors.append(
                "Kalshi adapter requires a private-key credential reference "
                "(KALSHI_API_PRIVATE_KEY_PEM, KALSHI_API_PRIVATE_KEY_PEM_PATH, "
                "KALSHI_PRIVATE_KEY, or KALSHI_PRIVATE_KEY_PATH)"
            )

    return errors


def _adapter_module_path_errors(data: dict[str, Any], *, check_exists: bool = False) -> list[str]:
    errors: list[str] = []
    module_path = data.get("adapter_module_path")
    if not isinstance(module_path, str) or not module_path:
        errors.append("adapter_module_path is required")
        return errors

    if _has_stub_marker(module_path):
        errors.append("adapter_module_path contains a banned stub/test/dummy/fixture marker")

    try:
        resolved = _safe_relative_path(module_path, DUMMY_ROOT)
    except ValueError as e:
        errors.append(f"adapter_module_path is unsafe: {e}")
        return errors

    if module_path not in ALLOWED_ADAPTER_MODULES:
        errors.append("adapter_module_path is not in the allowed real-adapter module list")

    if check_exists and not resolved.exists():
        errors.append(f"adapter_module_path does not exist: {module_path}")

    return errors


def _validate_adapter_descriptor(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        errors.append("descriptor must be a JSON object")
        return errors

    required = {
        "adapter_name",
        "broker",
        "adapter_module_path",
        "limit_order_endpoint_label",
        "adapter_type",
        "order_type_policy",
        "market_orders_allowed",
        "credential_source",
    }
    missing = required - set(data.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    # adapter_module_path is required; adapter_descriptor_path remains an
    # optional/alternative descriptor file reference if the operator uses one.
    if not data.get("adapter_module_path") and not data.get("adapter_descriptor_path"):
        errors.append("either adapter_module_path or adapter_descriptor_path is required")

    # Broker check.
    if data.get("broker") != "KALSHI":
        errors.append("broker must be 'KALSHI'")

    # Type/policy checks.
    if data.get("adapter_type") != "LiveBrokerFirewall":
        errors.append("adapter_type must be 'LiveBrokerFirewall'")
    if data.get("order_type_policy") != "LIMIT_ONLY":
        errors.append("order_type_policy must be 'LIMIT_ONLY'")
    if data.get("market_orders_allowed") is not False:
        errors.append("market_orders_allowed must be false")
    if data.get("credential_source") not in {"env_ref", "external_secret_ref"}:
        errors.append("credential_source must be 'env_ref' or 'external_secret_ref'")

    errors.extend(_adapter_module_path_errors(data))
    errors.extend(_credential_reference_errors(data))

    # Optional endpoint/base URL env ref.
    endpoint_ref = data.get("endpoint_env_ref")
    if endpoint_ref is not None:
        if not isinstance(endpoint_ref, str) or not endpoint_ref:
            errors.append("endpoint_env_ref must be a non-empty string")
        elif not re.fullmatch(r"[A-Z_][A-Z0-9_]*", endpoint_ref):
            errors.append(
                "endpoint_env_ref must be an env-var-style reference (uppercase/underscore/digits)"
            )
        elif _looks_like_secret(endpoint_ref):
            errors.append("endpoint_env_ref appears to contain a raw secret; use a reference name only")

    # Reject inlined secrets anywhere in the descriptor except reference/path
    # fields, which are intentionally uppercase env-var names.
    skip_secret_keys = {
        "credential_reference_name",
        "credential_reference_names",
        "adapter_module_path",
        "endpoint_env_ref",
    }
    for key, value in data.items():
        if key in skip_secret_keys:
            continue
        if isinstance(value, str) and _looks_like_secret(value):
            errors.append(f"field '{key}' appears to contain a raw secret; use a reference instead")

    # Reject stub/test/dummy/fixture markers in real-adapter fields.
    checked_keys = [
        "adapter_name",
        "broker",
        "adapter_module_path",
        "adapter_type",
        "order_type_policy",
        "limit_order_endpoint_label",
        "credential_source",
        "credential_reference_name",
    ]
    for key in checked_keys:
        value = data.get(key)
        if isinstance(value, str) and _has_stub_marker(value):
            errors.append(f"field '{key}' contains a banned stub/test/dummy/fixture marker")

    return errors


def _validate_live_submit(data: dict[str, Any]) -> list[str]:
    """Delegate to the shared live-submit state model validator."""
    return validate_operator_one_proof_enabled(data).errors


def _validate_strict_caps(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("order_type_policy") != "LIMIT_ONLY":
        errors.append("order_type_policy must be 'LIMIT_ONLY'")
    if data.get("market_orders_allowed") is not False:
        errors.append("market_orders_allowed must be false")
    if data.get("kill_switch_enabled") is not True:
        errors.append("kill_switch_enabled must be true")
    count = data.get("max_order_count")
    if not isinstance(count, int) or count > 1 or count < 1:
        errors.append("max_order_count must be 1 for the first proof")
    size = data.get("max_order_size")
    if not isinstance(size, int) or size > STRICT_MAX_ORDER_SIZE_CENTS or size < 1:
        errors.append(f"max_order_size must be between 1 and {STRICT_MAX_ORDER_SIZE_CENTS} cents")
    daily = data.get("max_daily_loss")
    if not isinstance(daily, int) or daily > STRICT_MAX_DAILY_LOSS_CENTS or daily < 1:
        errors.append(f"max_daily_loss must be between 1 and {STRICT_MAX_DAILY_LOSS_CENTS} cents")
    exposure = data.get("max_open_exposure")
    if not isinstance(exposure, int) or exposure > STRICT_MAX_OPEN_EXPOSURE_CENTS or exposure < 1:
        errors.append(
            f"max_open_exposure must be between 1 and {STRICT_MAX_OPEN_EXPOSURE_CENTS} cents"
        )

    # Legacy fields must stay aligned if present.
    if "allow_market_orders" in data and data["allow_market_orders"] is not False:
        errors.append("legacy allow_market_orders must be false")
    if "limit_orders_only" in data and data["limit_orders_only"] is not True:
        errors.append("legacy limit_orders_only must be true")
    if "kill_switch_required" in data and data["kill_switch_required"] is not True:
        errors.append("legacy kill_switch_required must be true")

    for key in ("operator", "reason", "expiry"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f"{key} must be a non-empty string")
    if not _is_iso_timestamp(data.get("expiry", "")):
        errors.append("expiry must be a valid ISO-8601 timestamp")
    return errors


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_adapter_contract(module_path: str) -> dict[str, Any]:
    """No-contact contract check: import the module and verify the adapter class.

    The module is executed, so real adapters must not perform any network I/O at
    import time. We only look for the expected class and, if provided, call a
    no-network ``validate_environment()`` hook.
    """
    result: dict[str, Any] = {
        "module_path": module_path,
        "exists": False,
        "importable": False,
        "class_present": False,
        "class_name": None,
        "validate_environment_ok": False,
        "contract_satisfied": False,
        "errors": [],
    }
    if not module_path:
        result["errors"].append("empty adapter_module_path")
        return result

    try:
        resolved = _safe_relative_path(module_path, DUMMY_ROOT)
    except ValueError as e:
        result["errors"].append(f"adapter_module_path is unsafe: {e}")
        return result

    if not resolved.exists():
        result["errors"].append(f"adapter module file not found: {module_path}")
        return result

    result["exists"] = True

    try:
        mod_name = module_path.replace("\\", "/").replace("/", ".").rstrip(".py")
        spec = importlib.util.spec_from_file_location(mod_name, resolved)
        if spec is None or spec.loader is None:
            raise ImportError("could not create module spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        result["errors"].append(f"adapter module import failed: {type(e).__name__}: {e}")
        return result

    result["importable"] = True

    class_name: str | None = None
    for name in ALLOWED_ADAPTER_CLASS_NAMES:
        if hasattr(module, name):
            class_name = name
            break
    if class_name is None:
        result["errors"].append(
            f"adapter module must expose one of {sorted(ALLOWED_ADAPTER_CLASS_NAMES)}"
        )
        return result

    result["class_present"] = True
    result["class_name"] = class_name
    adapter_class = getattr(module, class_name)

    if hasattr(adapter_class, "validate_environment"):
        try:
            adapter_class.validate_environment()
            result["validate_environment_ok"] = True
        except TypeError:
            # Possibly an instance method; try a no-arg instantiation.
            try:
                inst = adapter_class()
                inst.validate_environment()
                result["validate_environment_ok"] = True
            except Exception as e2:
                result["errors"].append(
                    f"adapter validate_environment() failed: {type(e2).__name__}: {e2}"
                )
                return result
        except Exception as e:
            result["errors"].append(
                f"adapter validate_environment() failed: {type(e).__name__}: {e}"
            )
            return result

    result["contract_satisfied"] = True
    return result


def _env_refs_present(refs: list[str]) -> list[str]:
    """Return env ref names that are set in the environment without reading values."""
    return [ref for ref in refs if ref not in os.environ]


def _credential_env_status(refs: list[str]) -> tuple[list[str], list[str]]:
    """Return (present, missing) env ref names without exposing values."""
    present = [ref for ref in refs if ref in os.environ]
    missing = [ref for ref in refs if ref not in os.environ]
    return present, missing


def _adapter_status() -> dict[str, Any]:
    data = _read_json(ADAPTER_DESCRIPTOR_PATH)
    errors = _validate_adapter_descriptor(data) if isinstance(data, dict) else ["descriptor not staged"]
    module_path = data.get("adapter_module_path") if isinstance(data, dict) else ""
    contract = (
        _load_adapter_contract(module_path)
        if isinstance(data, dict)
        else {"contract_satisfied": False, "errors": ["descriptor not staged"]}
    )
    if isinstance(data, dict) and not contract["contract_satisfied"]:
        errors.extend(contract["errors"])

    refs: list[str] = []
    if isinstance(data, dict):
        refs = _collect_credential_reference_names(data)
        endpoint_ref = data.get("endpoint_env_ref")
        if endpoint_ref:
            refs.append(endpoint_ref)

    credentials_present, credentials_missing = (
        _credential_env_status(refs) if isinstance(data, dict) else ([], [])
    )
    if isinstance(data, dict) and credentials_missing:
        errors.append(f"credential environment references missing: {credentials_missing}")

    return {
        "path": str(ADAPTER_DESCRIPTOR_PATH),
        "exists": ADAPTER_DESCRIPTOR_PATH.exists(),
        "hash": _sha256_file(ADAPTER_DESCRIPTOR_PATH),
        "staged": isinstance(data, dict),
        "valid": isinstance(data, dict) and not errors,
        "errors": errors if isinstance(data, dict) else [],
        "contract": contract,
        "module_importable": contract.get("importable", False),
        "module_import_error": (contract["errors"][0] if contract.get("errors") else None),
        "broker_contact": False,
        "credentials_present": credentials_present,
        "credentials_missing": credentials_missing,
    }


def _live_submit_status() -> dict[str, Any]:
    data = _read_json(LIVE_SUBMIT_PATH)
    errors = _validate_live_submit(data) if isinstance(data, dict) else ["live_submit.json not found"]
    return {
        "path": str(LIVE_SUBMIT_PATH),
        "exists": LIVE_SUBMIT_PATH.exists(),
        "hash": _sha256_file(LIVE_SUBMIT_PATH),
        "enabled": bool(data.get("enabled")) if isinstance(data, dict) else False,
        "valid": isinstance(data, dict) and not errors,
        "errors": errors if isinstance(data, dict) else [],
    }


def _caps_status() -> dict[str, Any]:
    data = _read_json(CAPS_PATH)
    errors = _validate_strict_caps(data) if isinstance(data, dict) else ["caps.json not found"]
    return {
        "path": str(CAPS_PATH),
        "exists": CAPS_PATH.exists(),
        "hash": _sha256_file(CAPS_PATH),
        "strict": isinstance(data, dict) and not errors,
        "valid": isinstance(data, dict) and not errors,
        "errors": errors if isinstance(data, dict) else [],
    }


def _approval_status() -> dict[str, Any]:
    return {
        "path": str(APPROVAL_PATH),
        "exists": APPROVAL_PATH.exists(),
    }


def _command_seal_status() -> dict[str, Any]:
    """Read-only command-seal check via the existing one-shot-check CLI path."""
    safety = [
        "read-only one-shot-check",
        "no broker contact",
        "no order placement",
        "shell=False",
    ]
    result = _run_script(
        FULL_COMPLETION,
        ["one-shot-check"],
        safety_notes=safety,
    )
    text = (result.get("stdout") or "").lower()
    ready = result["ok"] and ("ready" in text or "armable" in text or "command seal" in text)
    blocked = "blocked" in text or not ready
    return {
        "ok": result["ok"],
        "ready": ready,
        "blocked": blocked,
        "result": result,
    }


@router.get("/external-prereqs/status")
async def external_prereqs_status() -> dict[str, Any]:
    adapter = _adapter_status()
    live_submit = _live_submit_status()
    caps = _caps_status()
    approval = _approval_status()
    seal = _command_seal_status()
    blockers = [
        *(["adapter descriptor not valid"] if not adapter["valid"] else []),
        *(["live-submit not enabled/valid"] if not live_submit["valid"] else []),
        *(["strict caps not confirmed"] if not caps["valid"] else []),
        *(["approval not installed"] if not approval["exists"] else []),
        *(["command seal not ready"] if seal["blocked"] else []),
    ]
    return {
        "ok": not blockers,
        "adapter": adapter,
        "live_submit": live_submit,
        "caps": caps,
        "approval": approval,
        "command_seal": seal,
        "blockers": blockers,
        "safety_notes": [
            "read-only status",
            "no broker contact",
            "no order placement",
        ],
    }


@router.post("/external-prereqs/adapter/validate")
async def adapter_validate(body: AdapterDescriptorBody) -> dict[str, Any]:
    errors = _validate_adapter_descriptor(body.descriptor)
    return {
        "ok": not errors,
        "errors": errors,
        "descriptor_name": body.descriptor.get("adapter_name") if isinstance(body.descriptor, dict) else None,
        "safety_notes": [
            "no broker contact",
            "no order placement",
            "no secret logging",
        ],
    }


@router.post("/external-prereqs/adapter/register")
async def adapter_register(body: AdapterRegisterBody) -> dict[str, Any]:
    # Fail closed on missing confirmations.
    missing_checks = []
    if not body.operator_confirm_adapter_real:
        missing_checks.append("operator_confirm_adapter_real")
    if not body.operator_confirm_not_stub:
        missing_checks.append("operator_confirm_not_stub")
    if not body.operator_confirm_limit_only:
        missing_checks.append("operator_confirm_limit_only")
    if body.typed_confirmation != ADAPTER_TYPED_CONFIRMATION:
        missing_checks.append("typed_confirmation")
    if missing_checks:
        return {
            "ok": False,
            "errors": [f"missing confirmations: {missing_checks}"],
            "safety_notes": ["registration blocked: confirmation incomplete"],
        }

    errors = _validate_adapter_descriptor(body.descriptor)
    if errors:
        return {"ok": False, "errors": errors, "safety_notes": ["registration blocked: descriptor invalid"]}

    module_errors = _adapter_module_path_errors(body.descriptor, check_exists=True)
    if module_errors:
        return {
            "ok": False,
            "errors": module_errors,
            "safety_notes": ["registration blocked: adapter module not found"],
        }

    hash_before = _sha256_file(ADAPTER_DESCRIPTOR_PATH)
    backup = _atomic_write_json(ADAPTER_DESCRIPTOR_PATH, body.descriptor)
    hash_after = _sha256_file(ADAPTER_DESCRIPTOR_PATH)
    return {
        "ok": True,
        "path": str(ADAPTER_DESCRIPTOR_PATH),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "backup_path": str(backup) if backup else None,
        "safety_notes": [
            "descriptor staged",
            "no broker contact",
            "no order placement",
            "no raw secrets stored",
        ],
    }


@router.post("/external-prereqs/adapter/smoke")
async def adapter_smoke(body: AdapterDescriptorBody) -> dict[str, Any]:
    """No-contact smoke check. We validate the descriptor only."""
    errors = _validate_adapter_descriptor(body.descriptor)
    return {
        "ok": not errors,
        "errors": errors,
        "safety_notes": [
            "no broker contact",
            "no order placement",
            "no cancel",
            "descriptor-only validation",
        ],
    }


def _build_live_submit_config(body: LiveSubmitBody) -> dict[str, Any]:
    return {
        "enabled": body.enabled,
        "operator": body.operator,
        "reason": body.reason,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiry": body.expiry,
        "proof_scope": body.proof_scope,
        "weaken_gates": False,
        "auto_run": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "scale_enabled": False,
        "autonomy_enabled": False,
        "explicit_acknowledgement": LIVE_SUBMIT_REQUIRED_ACK,
    }


@router.post("/external-prereqs/live-submit/preview")
async def live_submit_preview(body: LiveSubmitBody) -> dict[str, Any]:
    proposed = _build_live_submit_config(body)
    errors = _validate_live_submit(proposed)
    return {
        "ok": not errors,
        "proposed": proposed,
        "errors": errors,
        "hash_after": _sha256_canonical(proposed),
        "will_write": False,
        "safety_notes": ["preview only", "no config written"],
    }


@router.post("/external-prereqs/live-submit/write")
async def live_submit_write(body: LiveSubmitBody) -> dict[str, Any]:
    if body.typed_confirmation != LIVE_SUBMIT_TYPED_CONFIRMATION:
        return {
            "ok": False,
            "errors": ["typed confirmation does not match the required sentence"],
            "safety_notes": ["write blocked: confirmation incomplete"],
        }
    proposed = _build_live_submit_config(body)
    errors = _validate_live_submit(proposed)
    if errors:
        return {"ok": False, "errors": errors, "safety_notes": ["write blocked: validation failed"]}

    hash_before = _sha256_file(LIVE_SUBMIT_PATH)
    backup = _atomic_write_json(LIVE_SUBMIT_PATH, proposed)
    hash_after = _sha256_file(LIVE_SUBMIT_PATH)
    return {
        "ok": True,
        "path": str(LIVE_SUBMIT_PATH),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "backup_path": str(backup) if backup else None,
        "safety_notes": [
            "live_submit.json written",
            "backup created",
            "no live proof run",
            "no broker contact",
        ],
    }


@router.post("/external-prereqs/live-submit/disable")
async def live_submit_disable() -> dict[str, Any]:
    existing = _read_json(LIVE_SUBMIT_PATH) or {}
    if not isinstance(existing, dict):
        existing = {}
    disabled = {
        **existing,
        "enabled": False,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reason": f"operator relock: {existing.get('reason', 'none')}",
    }
    # Remove the explicit ack so the firewall cannot treat this as enabled.
    disabled.pop("explicit_acknowledgement", None)

    hash_before = _sha256_file(LIVE_SUBMIT_PATH)
    backup = _atomic_write_json(LIVE_SUBMIT_PATH, disabled)
    hash_after = _sha256_file(LIVE_SUBMIT_PATH)
    return {
        "ok": True,
        "path": str(LIVE_SUBMIT_PATH),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "backup_path": str(backup) if backup else None,
        "safety_notes": ["live-submit disabled", "explicit acknowledgement removed", "backup created"],
    }


def _build_caps_config(body: CapsBody) -> dict[str, Any]:
    # Start from existing caps so we do not break the engine's CapConfig loader.
    existing = _read_json(CAPS_PATH)
    if not isinstance(existing, dict):
        existing = {}
    merged = {
        **existing,
        "max_order_count": body.max_order_count,
        "max_order_size": body.max_order_size,
        "order_type_policy": body.order_type_policy,
        "market_orders_allowed": body.market_orders_allowed,
        "kill_switch_enabled": body.kill_switch_enabled,
        "max_daily_loss": body.max_daily_loss,
        "max_open_exposure": body.max_open_exposure,
        "operator": body.operator,
        "reason": body.reason,
        "expiry": body.expiry,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "proof_scope": "one_controlled_proof",
        # Keep legacy fields aligned so existing consumers stay safe.
        "allow_market_orders": False,
        "limit_orders_only": True,
        "kill_switch_required": True,
        "max_single_order_cents": min(body.max_order_size, existing.get("max_single_order_cents", body.max_order_size)),
        "max_daily_loss_cents": min(body.max_daily_loss, existing.get("max_daily_loss_cents", body.max_daily_loss)),
        "max_total_live_exposure_cents": min(body.max_open_exposure, existing.get("max_total_live_exposure_cents", body.max_open_exposure)),
    }
    return merged


@router.post("/external-prereqs/caps/preview")
async def caps_preview(body: CapsBody) -> dict[str, Any]:
    proposed = _build_caps_config(body)
    errors = _validate_strict_caps(proposed)
    return {
        "ok": not errors,
        "proposed": proposed,
        "errors": errors,
        "hash_after": _sha256_canonical(proposed),
        "will_write": False,
        "safety_notes": ["preview only", "no config written"],
    }


@router.post("/external-prereqs/caps/write")
async def caps_write(body: CapsBody) -> dict[str, Any]:
    if body.typed_confirmation != CAPS_TYPED_CONFIRMATION:
        return {
            "ok": False,
            "errors": ["typed confirmation does not match the required sentence"],
            "safety_notes": ["write blocked: confirmation incomplete"],
        }
    proposed = _build_caps_config(body)
    errors = _validate_strict_caps(proposed)
    if errors:
        return {"ok": False, "errors": errors, "safety_notes": ["write blocked: validation failed"]}

    hash_before = _sha256_file(CAPS_PATH)
    backup = _atomic_write_json(CAPS_PATH, proposed)
    hash_after = _sha256_file(CAPS_PATH)
    return {
        "ok": True,
        "path": str(CAPS_PATH),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "backup_path": str(backup) if backup else None,
        "safety_notes": [
            "strict caps written",
            "backup created",
            "no live proof run",
            "no broker contact",
        ],
    }


@router.post("/external-prereqs/caps/relock")
async def caps_relock() -> dict[str, Any]:
    existing = _read_json(CAPS_PATH)
    if not isinstance(existing, dict):
        existing = {}
    safe = {
        **existing,
        "max_order_count": 0,
        "max_order_size": 0,
        "order_type_policy": "LIMIT_ONLY",
        "market_orders_allowed": False,
        "kill_switch_enabled": True,
        "max_daily_loss": 0,
        "max_open_exposure": 0,
        "operator": "operator",
        "reason": "relock: caps reset to safe disabled state",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiry": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "proof_scope": "none",
        "allow_market_orders": False,
        "limit_orders_only": True,
        "kill_switch_required": True,
    }
    hash_before = _sha256_file(CAPS_PATH)
    backup = _atomic_write_json(CAPS_PATH, safe)
    hash_after = _sha256_file(CAPS_PATH)
    return {
        "ok": True,
        "path": str(CAPS_PATH),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "backup_path": str(backup) if backup else None,
        "safety_notes": ["caps relocked", "zero exposure", "backup created"],
    }


@router.post("/external-prereqs/check-all")
async def external_prereqs_check_all() -> dict[str, Any]:
    adapter = _adapter_status()
    live_submit = _live_submit_status()
    caps = _caps_status()
    approval = _approval_status()
    seal = _command_seal_status()

    blockers: list[str] = []
    if not adapter["valid"]:
        blockers.append(f"adapter: {adapter['errors'][0] if adapter['errors'] else 'not valid'}")
    if not live_submit["valid"]:
        blockers.append(f"live-submit: {live_submit['errors'][0] if live_submit['errors'] else 'not valid'}")
    if not caps["valid"]:
        blockers.append(f"caps: {caps['errors'][0] if caps['errors'] else 'not strict'}")
    if not approval["exists"]:
        blockers.append("approval: not installed")
    if seal["blocked"]:
        blockers.append("command-seal: not ready")

    return {
        "ok": not blockers,
        "ready": not blockers,
        "blockers": blockers,
        "adapter": adapter,
        "live_submit": live_submit,
        "caps": caps,
        "approval": approval,
        "command_seal": seal,
        "safety_notes": [
            "combined read-only validation",
            "no broker contact",
            "no order placement",
        ],
    }
# Resolve Pydantic forward references now that all types are importable.
AdapterDescriptorBody.model_rebuild()
AdapterRegisterBody.model_rebuild()
LiveSubmitBody.model_rebuild()
CapsBody.model_rebuild()
SecondProofAuthorityActivateBody.model_rebuild()


def _sha256_file(path: str) -> str | None:
    from pathlib import Path
    import hashlib
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()
