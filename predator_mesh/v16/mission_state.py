"""Concise Dummy mission-state summary for V16."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v16.terrain_truth import RealTerrainTruthResolution


class MissionStateVerdict(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


@dataclass(frozen=True)
class MissionStateBlocker:
    code: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "description": self.description}


@dataclass(frozen=True)
class MissionStateNextAction:
    action: str

    def to_dict(self) -> dict[str, str]:
        return {"action": self.action}


@dataclass(frozen=True)
class DummyMissionState:
    credential_shape: str
    auth_probe: str
    config_binding: str
    market_discovery: str
    orderbook_snapshot: str
    terrain_truth_verdict: str
    replay_mode: str
    liquidity_terrain_mode: str
    live_submit_disabled: bool
    caps_unchanged: bool
    no_direct_order_cancel_bypass: bool
    source_adapter_remaining_modes: list[str]
    blocker: MissionStateBlocker
    next_action: MissionStateNextAction

    @classmethod
    def from_truth(cls, truth: RealTerrainTruthResolution) -> "DummyMissionState":
        is_pass = truth.verdict.startswith("PASS")
        blocker = MissionStateBlocker("NONE" if is_pass else truth.verdict, "No current blocker." if is_pass else "See terrain truth verdict.")
        next_action = MissionStateNextAction("Proceed to operator review; live submit remains disabled." if is_pass else "Repair the explicit partial blocker and regenerate V16 proof.")
        return cls(
            credential_shape=truth.evidence.input.credential_shape_state,
            auth_probe=truth.evidence.input.auth_probe_state,
            config_binding=truth.evidence.input.config_binding_state,
            market_discovery=truth.evidence.input.market_discovery_state,
            orderbook_snapshot=truth.evidence.input.orderbook_snapshot_state,
            terrain_truth_verdict=truth.verdict,
            replay_mode=truth.evidence.input.replay_state,
            liquidity_terrain_mode=truth.evidence.input.orderbook_snapshot_state,
            live_submit_disabled=True,
            caps_unchanged=True,
            no_direct_order_cancel_bypass=True,
            source_adapter_remaining_modes=["weather", "sports", "macro", "finance", "commodities", "crypto"],
            blocker=blocker,
            next_action=next_action,
        )

    def mission_verdict(self) -> str:
        if self.terrain_truth_verdict.startswith("FAIL"):
            return MissionStateVerdict.FAIL.value
        if self.terrain_truth_verdict.startswith("PASS"):
            return MissionStateVerdict.PASS.value
        return MissionStateVerdict.PARTIAL.value

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Dummy Mission State",
            "mission_state_verdict": self.mission_verdict(),
            "credential_shape": self.credential_shape,
            "auth_probe": self.auth_probe,
            "config_binding": self.config_binding,
            "market_discovery": self.market_discovery,
            "orderbook_snapshot": self.orderbook_snapshot,
            "terrain_truth_verdict": self.terrain_truth_verdict,
            "replay_mode": self.replay_mode,
            "liquidity_proof_terrain_mode": self.liquidity_terrain_mode,
            "live_submit_disabled": self.live_submit_disabled,
            "caps_unchanged": self.caps_unchanged,
            "no_direct_order_cancel_bypass": self.no_direct_order_cancel_bypass,
            "source_adapter_remaining_modes": self.source_adapter_remaining_modes,
            "current_blocker": self.blocker.to_dict(),
            "next_action": self.next_action.to_dict(),
            "secret_values_exposed": False,
            "verdict": self.mission_verdict(),
        }
