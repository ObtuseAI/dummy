"""Shared proof-lock helpers.

Detect whether a real broker attempt has already been consumed so that Dummy
never accidentally repeats it. Reads only lightweight json/pathlib; no secrets
are logged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REAL_PROOF_REGISTRY_PATH = Path("artifacts/dummy/real_proof_registry.json")


def _load_real_proof_registry() -> dict[str, Any] | None:
    if not REAL_PROOF_REGISTRY_PATH.exists():
        return None
    try:
        data = json.loads(REAL_PROOF_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _v298_final_report_path() -> Path:
    return Path("artifacts/dummy/final_report_v298.json")


def _load_v298_final_report() -> dict[str, Any] | None:
    path = _v298_final_report_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _v298_indicates_real_attempt(data: dict[str, Any]) -> bool:
    status = str(data.get("execute_once_final_proof_runner_v7_controller_status", ""))
    if status != "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED":
        return False
    return bool(
        data.get("real_broker_contacted") is True
        or int(data.get("real_live_orders_submitted_count", 0) or 0) > 0
        or data.get("broker_rejection_captured") is True
    )


def real_proof_attempt_exists() -> bool:
    """Return True if a real broker attempt has already been consumed.

    Checked in two places:
    1. The preserved real-proof registry written by the operator appliance.
    2. The existing v298 final report, but only when it is not a default dry
       artifact and the autolocked status reflects real broker contact.
    """
    registry = _load_real_proof_registry()
    if registry is not None and registry.get("latest_real_broker_contacted") is True:
        return True

    v298 = _load_v298_final_report()
    if v298 is None:
        return False

    # Ignore default dry artifacts that can never count as a real attempt.
    if v298.get("arm_state") == "NOT_ARMED_DRY_DEFAULT":
        return False
    if v298.get("non_broker_double_used") is True:
        return False

    return _v298_indicates_real_attempt(v298)


def proof_lock_clear() -> bool:
    return not real_proof_attempt_exists()


def preserved_evidence_dir() -> str | None:
    registry = _load_real_proof_registry()
    if registry is None:
        return None
    return registry.get("latest_real_broker_proof_evidence_dir")


def load_real_proof_registry() -> dict[str, Any] | None:
    """Public read-only accessor for the real-proof registry."""
    return _load_real_proof_registry()
