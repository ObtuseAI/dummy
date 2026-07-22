"""V15 liquidity launch readiness matrix V2 and micro-order launch gate V2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from core.caps_authority import evaluate_caps_authority
from predator_mesh.v14.credential_forensics import KalshiCredentialForensics
from predator_mesh.v15.retry_gate_v2 import RealTerrainRetryGateV2
from predator_mesh.v15.terrain_closure_v3 import RealOrderbookTerrainClosureV3

ROOT = Path(__file__).resolve().parents[2]


class MicroOrderLaunchGateV2(str, Enum):
    READY_FOR_OPERATOR_ARMED_MICRO_ORDER_REHEARSAL = "READY_FOR_OPERATOR_ARMED_MICRO_ORDER_REHEARSAL"
    READY_ONLY_AFTER_CREDENTIAL_SHAPE_REPAIR = "READY_ONLY_AFTER_CREDENTIAL_SHAPE_REPAIR"
    READY_ONLY_AFTER_AUTH_REPAIR = "READY_ONLY_AFTER_AUTH_REPAIR"
    READY_ONLY_AFTER_REAL_TERRAIN_PROOF = "READY_ONLY_AFTER_REAL_TERRAIN_PROOF"
    BLOCKED_LIVE_SUBMIT_DISABLED = "BLOCKED_LIVE_SUBMIT_DISABLED"
    BLOCKED_CAPS_NOT_VERIFIED = "BLOCKED_CAPS_NOT_VERIFIED"
    BLOCKED_CAPS_AUTHORITY_MIGRATION_REQUIRED = "BLOCKED_CAPS_AUTHORITY_MIGRATION_REQUIRED"
    NOT_READY = "NOT_READY"


@dataclass(frozen=True)
class CredentialShapeReadiness:
    ready: bool
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {"ready": self.ready, "state": self.state}


@dataclass(frozen=True)
class AuthReadiness:
    ready: bool
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {"ready": self.ready, "state": self.state}


@dataclass(frozen=True)
class RealTerrainReadiness:
    ready: bool
    terrain_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {"ready": self.ready, "terrain_mode": self.terrain_mode}


def _live_submit_disabled() -> bool:
    path = ROOT / "configs" / "live_submit.json"
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return True
    return data.get("enabled") is not True


def _caps_unmodified() -> bool:
    """Return whether caps match the current protected v2 baseline.

    Worktree cleanliness is not an authority proof.  The exact versioned raw
    hash is, and the separate operator-registration predicate is checked by
    ``gate_output`` below.
    """

    return evaluate_caps_authority().config_integrity_valid


class LiquidityLaunchReadinessMatrixV2:
    def __init__(
        self,
        *,
        forensics_report: dict[str, Any] | None = None,
        retry_gate: RealTerrainRetryGateV2 | None = None,
        terrain_closure: RealOrderbookTerrainClosureV3 | None = None,
    ) -> None:
        self.forensics_report = forensics_report or KalshiCredentialForensics().to_report()
        self.retry_gate = retry_gate or RealTerrainRetryGateV2(forensics_report=self.forensics_report)
        self.terrain_closure = terrain_closure or RealOrderbookTerrainClosureV3(forensics_report=self.forensics_report, retry_gate=self.retry_gate)

    def credential_shape_readiness(self) -> CredentialShapeReadiness:
        state = self.retry_gate.shape_state().value
        return CredentialShapeReadiness(ready=state == "SHAPE_VALID", state=state)

    def auth_readiness(self) -> AuthReadiness:
        state = self.retry_gate.auth_state().value
        return AuthReadiness(ready=state == "AUTH_PASS", state=state)

    def real_terrain_readiness(self) -> RealTerrainReadiness:
        mode = self.terrain_closure.terrain_mode()
        return RealTerrainReadiness(ready=mode == "PASS_REAL_TERRAIN", terrain_mode=mode)

    def gate_output(self) -> MicroOrderLaunchGateV2:
        if not _live_submit_disabled():
            return MicroOrderLaunchGateV2.BLOCKED_LIVE_SUBMIT_DISABLED
        if not _caps_unmodified():
            return MicroOrderLaunchGateV2.BLOCKED_CAPS_NOT_VERIFIED
        if not evaluate_caps_authority().authority_registration_valid:
            return MicroOrderLaunchGateV2.BLOCKED_CAPS_AUTHORITY_MIGRATION_REQUIRED

        cred = self.credential_shape_readiness()
        if not cred.ready:
            return MicroOrderLaunchGateV2.READY_ONLY_AFTER_CREDENTIAL_SHAPE_REPAIR

        auth = self.auth_readiness()
        if not auth.ready:
            return MicroOrderLaunchGateV2.READY_ONLY_AFTER_AUTH_REPAIR

        terrain = self.real_terrain_readiness()
        if not terrain.ready:
            return MicroOrderLaunchGateV2.READY_ONLY_AFTER_REAL_TERRAIN_PROOF

        return MicroOrderLaunchGateV2.READY_FOR_OPERATOR_ARMED_MICRO_ORDER_REHEARSAL

    def blockers(self) -> list[str]:
        blockers: list[str] = []
        if not _live_submit_disabled():
            blockers.append("LIVE_SUBMIT_ENABLED")
        if not _caps_unmodified():
            blockers.append("CAPS_JSON_MODIFIED")
        caps_authority = evaluate_caps_authority()
        if not caps_authority.authority_registration_valid:
            blockers.append("CAPS_AUTHORITY_MIGRATION_REQUIRED")
        if not self.credential_shape_readiness().ready:
            blockers.append("CREDENTIAL_SHAPE_NOT_READY")
        if not self.auth_readiness().ready:
            blockers.append("AUTH_NOT_PROVEN")
        if not self.real_terrain_readiness().ready:
            blockers.append("REAL_TERRAIN_NOT_PROVEN")
        return blockers

    def to_report(self) -> dict[str, Any]:
        gate = self.gate_output()
        blockers = self.blockers()
        caps_authority = evaluate_caps_authority()
        categories = {
            "credential_shape_readiness": 1.0 if self.credential_shape_readiness().ready else 0.0,
            "auth_readiness": 1.0 if self.auth_readiness().ready else 0.0,
            "real_terrain_readiness": 1.0 if self.real_terrain_readiness().ready else 0.0,
            "live_submit_disabled": 1.0 if _live_submit_disabled() else 0.0,
            "caps_unmodified": 1.0 if _caps_unmodified() else 0.0,
            "caps_authority_registered": 1.0 if caps_authority.authority_registration_valid else 0.0,
        }
        readiness_score = round(sum(categories.values()) / len(categories), 4)
        return {
            "workstream": "V15: Liquidity Launch Readiness Matrix V2",
            "categories": categories,
            "readiness_score": readiness_score,
            "credential_shape_readiness": self.credential_shape_readiness().to_dict(),
            "auth_readiness": self.auth_readiness().to_dict(),
            "real_terrain_readiness": self.real_terrain_readiness().to_dict(),
            "live_submit_disabled": _live_submit_disabled(),
            "caps_unmodified": _caps_unmodified(),
            "caps_authority": caps_authority.to_dict(),
            "legacy_caps_authority_invalidated": caps_authority.legacy_authority_invalidated,
            "execution_authority": False,
            "blockers": blockers,
            "gate_output": gate.value,
            "operator_armed_micro_order_ready": gate == MicroOrderLaunchGateV2.READY_FOR_OPERATOR_ARMED_MICRO_ORDER_REHEARSAL,
            "rehearsal_only": True,
            "not_a_live_order_trigger": True,
            "verdict": "PASS" if gate == MicroOrderLaunchGateV2.READY_FOR_OPERATOR_ARMED_MICRO_ORDER_REHEARSAL else "PARTIAL",
        }
