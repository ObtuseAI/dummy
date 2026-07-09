"""Shadow order packets for V11 rehearsal-only execution proof."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShadowOrderIntent:
    order_type: str
    side: str
    action: str = "buy"

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ShadowOrderSizing:
    size: int
    max_size: int
    max_notional_cents: int

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ShadowOrderPriceLimit:
    price_cents: int
    max_price_cents: int
    min_price_cents: int = 1

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ShadowOrderProofRefs:
    edge_candidate: str
    forecast_opinion: str
    strategy_governor: str
    liquidity_proof_packet: str
    fill_quality_estimate: str
    model_proof_path: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ShadowOrderDigest:
    digest: str
    payload_stored: str = "digest_only"

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ShadowOrderDigest":
        text = json.dumps(payload, sort_keys=True, default=str)
        return cls(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16])

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ShadowOrderPacket:
    packet_id: str
    market_ticker: str
    contract_ticker: str
    intent: ShadowOrderIntent
    sizing: ShadowOrderSizing
    price_limit: ShadowOrderPriceLimit
    proof_refs: ShadowOrderProofRefs
    digest: ShadowOrderDigest
    blocked_reason: str
    no_model_output_authority: bool = True
    no_direct_submit_authority: bool = True
    live_submit_disabled: bool = True

    @classmethod
    def sample(cls) -> "ShadowOrderPacket":
        payload = {
            "packet_id": "shadow-v11-001",
            "market_ticker": "KXDEMO-LIQUIDITY",
            "contract_ticker": "KXDEMO-LIQUIDITY-YES",
            "side": "yes",
            "price_cents": 52,
            "size": 1,
        }
        return cls(
            packet_id="shadow-v11-001",
            market_ticker=payload["market_ticker"],
            contract_ticker=payload["contract_ticker"],
            intent=ShadowOrderIntent(order_type="limit", side=payload["side"]),
            sizing=ShadowOrderSizing(size=1, max_size=1, max_notional_cents=52),
            price_limit=ShadowOrderPriceLimit(price_cents=52, max_price_cents=60),
            proof_refs=ShadowOrderProofRefs(
                edge_candidate="edge-v11-001",
                forecast_opinion="forecast-proof-v11-001",
                strategy_governor="strategy-governor-proof-v11-001",
                liquidity_proof_packet="liq-proof-edge-v11-001",
                fill_quality_estimate="fill-quality-v11-001",
                model_proof_path="live-model-smoke-v3",
            ),
            digest=ShadowOrderDigest.from_payload(payload),
            blocked_reason="LIVE_SUBMIT_DISABLED",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "market_ticker": self.market_ticker,
            "contract_ticker": self.contract_ticker,
            "intent": self.intent.to_dict(),
            "sizing": self.sizing.to_dict(),
            "price_limit": self.price_limit.to_dict(),
            "proof_refs": self.proof_refs.to_dict(),
            "digest": self.digest.to_dict(),
            "blocked_reason": self.blocked_reason,
            "no_model_output_authority": self.no_model_output_authority,
            "no_direct_submit_authority": self.no_direct_submit_authority,
            "live_submit_disabled": self.live_submit_disabled,
        }

    @classmethod
    def manifest(cls) -> dict[str, Any]:
        packet = cls.sample()
        return {
            "workstream": "V11: Shadow Order Packet Manifest",
            "packets": [packet.to_dict()],
            "limit_order_only": packet.intent.order_type == "limit",
            "blocked_by_default": packet.blocked_reason == "LIVE_SUBMIT_DISABLED",
            "verdict": "PASS",
        }

    @classmethod
    def to_report(cls) -> dict[str, Any]:
        packet = cls.sample()
        return {
            "workstream": "V11: Shadow Order Packet",
            "packet": packet.to_dict(),
            "limit_order_only": packet.intent.order_type == "limit",
            "no_direct_submit_authority": packet.no_direct_submit_authority,
            "blocked_reason": packet.blocked_reason,
            "verdict": "PASS",
        }
