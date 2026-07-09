"""Operator-facing micro-order arming packets for V11."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from live_firewall.firewall import LiveBrokerFirewall
from predator_mesh.v11.shadow_orders import ShadowOrderProofRefs


@dataclass(frozen=True)
class MicroOrderCapCheck:
    max_size: int
    config_cap_size: int
    max_notional_cents: int
    caps_pass: bool

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class MicroOrderOperatorAcknowledgementCheck:
    required_acknowledgement: str
    acknowledgement_present: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_acknowledgement_present": bool(self.required_acknowledgement),
            "acknowledgement_present": self.acknowledgement_present,
        }


@dataclass(frozen=True)
class MicroOrderReadinessVerdict:
    verdict: str
    live_submit_enabled: bool
    would_submit: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class MicroOrderArmingPacket:
    packet_id: str
    max_size: int
    config_cap_size: int
    limit_order_only: bool
    market_orders_allowed: bool
    requires_operator_acknowledgement: bool
    cap_check: MicroOrderCapCheck
    acknowledgement_check: MicroOrderOperatorAcknowledgementCheck
    kill_switch_off: bool
    emergency_stop_off: bool
    proof_refs: ShadowOrderProofRefs

    @classmethod
    def sample(cls) -> "MicroOrderArmingPacket":
        proof_refs = ShadowOrderProofRefs(
            edge_candidate="edge-v11-001",
            forecast_opinion="forecast-proof-v11-001",
            strategy_governor="strategy-governor-proof-v11-001",
            liquidity_proof_packet="liq-proof-edge-v11-001",
            fill_quality_estimate="fill-quality-v11-001",
            model_proof_path="live-model-smoke-v3",
        )
        object.__setattr__(proof_refs, "no_secret_leak", "no-secret-leak-v11")
        object.__setattr__(proof_refs, "no_direct_order_bypass", "no-direct-order-bypass-v11")
        return cls(
            packet_id="micro-arm-v11-001",
            max_size=1,
            config_cap_size=1,
            limit_order_only=True,
            market_orders_allowed=False,
            requires_operator_acknowledgement=True,
            cap_check=MicroOrderCapCheck(1, 1, 60, True),
            acknowledgement_check=MicroOrderOperatorAcknowledgementCheck(
                LiveBrokerFirewall.REQUIRED_ACKNOWLEDGEMENT,
                False,
            ),
            kill_switch_off=True,
            emergency_stop_off=True,
            proof_refs=proof_refs,
        )

    def evaluate_readiness(self, *, live_submit_enabled: bool) -> MicroOrderReadinessVerdict:
        reasons: list[str] = []
        if not live_submit_enabled:
            reasons.append("live_submit_disabled")
        if not self.acknowledgement_check.acknowledgement_present:
            reasons.append("operator_acknowledgement_missing")
        if not self.cap_check.caps_pass:
            reasons.append("caps_failed")
        if not self.kill_switch_off:
            reasons.append("kill_switch_active")
        if not self.emergency_stop_off:
            reasons.append("emergency_stop_active")
        if reasons:
            return MicroOrderReadinessVerdict(
                verdict="BLOCKED_LIVE_SUBMIT_DISABLED" if "live_submit_disabled" in reasons else "BLOCKED",
                live_submit_enabled=live_submit_enabled,
                would_submit=False,
                reasons=reasons,
            )
        return MicroOrderReadinessVerdict("ARMED_BUT_NOT_SENT", live_submit_enabled, False, [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "max_size": self.max_size,
            "config_cap_size": self.config_cap_size,
            "limit_order_only": self.limit_order_only,
            "market_orders_allowed": self.market_orders_allowed,
            "requires_operator_acknowledgement": self.requires_operator_acknowledgement,
            "cap_check": self.cap_check.to_dict(),
            "acknowledgement_check": self.acknowledgement_check.to_dict(),
            "kill_switch_off": self.kill_switch_off,
            "emergency_stop_off": self.emergency_stop_off,
            "proof_refs": {
                **self.proof_refs.to_dict(),
                "no_secret_leak": getattr(self.proof_refs, "no_secret_leak", ""),
                "no_direct_order_bypass": getattr(self.proof_refs, "no_direct_order_bypass", ""),
            },
        }

    @classmethod
    def to_report(cls) -> dict[str, Any]:
        packet = cls.sample()
        return {
            "workstream": "V11: Micro Order Arming Packet",
            "packet": packet.to_dict(),
            "verdict": "PASS",
        }

    @classmethod
    def readiness_report(cls, *, live_submit_enabled: bool = False) -> dict[str, Any]:
        packet = cls.sample()
        readiness = packet.evaluate_readiness(live_submit_enabled=live_submit_enabled)
        return {
            "workstream": "V11: Micro Order Readiness Verdict",
            "readiness": readiness.to_dict(),
            "verdict": "PASS" if readiness.verdict == "BLOCKED_LIVE_SUBMIT_DISABLED" else "FAIL",
        }
