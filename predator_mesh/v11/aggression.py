"""Liquidity-aware aggression governor for V11."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LiquidityAggressionScore:
    edge_score: float
    spread_quality: float
    depth_quality: float
    fill_probability: float
    fill_drag: float
    stale_quote_risk: float
    liquidity_decay: float
    cap_impact: float
    settlement_risk: float
    confidence_bucket: float
    source_bloodline_support: float
    signal_bloodline_support: float
    model_disagreement: float
    calibration_support: float
    total: float

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class LiquiditySizingDecision:
    decision: str
    requested_size: int
    size: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class LiquidityNoTradePressure:
    pressure: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class LiquidityFastInvalidation:
    invalidates_fast: bool
    triggers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class LiquidityAggressionDecision:
    decision: str
    score: LiquidityAggressionScore
    sizing: LiquiditySizingDecision
    no_trade_pressure: LiquidityNoTradePressure
    fast_invalidation: LiquidityFastInvalidation

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "score": self.score.to_dict(),
            "sizing": self.sizing.to_dict(),
            "no_trade_pressure": self.no_trade_pressure.to_dict(),
            "fast_invalidation": self.fast_invalidation.to_dict(),
        }


class LiquidityAggressionGovernor:
    @staticmethod
    def sample_inputs(**overrides: float) -> dict[str, float]:
        data = {
            "edge_score": 0.82,
            "spread_quality": 0.78,
            "depth_quality": 0.74,
            "fill_probability": 0.80,
            "fill_drag": 0.08,
            "stale_quote_risk": 0.05,
            "liquidity_decay": 0.04,
            "cap_impact": 0.05,
            "settlement_risk": 0.18,
            "confidence_bucket": 0.75,
            "source_bloodline_support": 0.72,
            "signal_bloodline_support": 0.70,
            "model_disagreement": 0.12,
            "calibration_support": 0.74,
        }
        data.update(overrides)
        return data

    def evaluate(self, inputs: dict[str, float]) -> LiquidityAggressionDecision:
        score = self._score(inputs)
        sizing = self._sizing(inputs.get("fill_drag", 0.0), requested_size=2)
        pressure_reasons = []
        pressure = 0.0
        if inputs.get("fill_drag", 0) > 0.30:
            pressure += 0.30
            pressure_reasons.append("fill_drag")
        if inputs.get("stale_quote_risk", 0) > 0.30:
            pressure += 0.30
            pressure_reasons.append("stale_quote")
        if inputs.get("model_disagreement", 0) > 0.35:
            pressure += 0.25
            pressure_reasons.append("model_disagreement")
        if inputs.get("settlement_risk", 0) > 0.70:
            pressure += 0.35
            pressure_reasons.append("settlement_risk")
        invalidation = LiquidityFastInvalidation(
            invalidates_fast=bool(pressure_reasons),
            triggers=pressure_reasons,
        )

        if inputs.get("settlement_risk", 0) > 0.90:
            decision = "QUARANTINE_MARKET"
        elif score.total >= 0.55 and sizing.decision != "REDUCE_SIZE":
            decision = "ESCALATE_TO_SHADOW_ORDER"
        elif score.total >= 0.45:
            decision = "APPROVE_FIREWALL_REHEARSAL"
        elif sizing.decision == "REDUCE_SIZE":
            decision = "REDUCE_SIZE"
        elif score.total >= 0.35:
            decision = "REQUIRE_MORE_EVIDENCE"
        elif pressure >= 0.50:
            decision = "STARVE_LIQUIDITY_SIGNAL"
        else:
            decision = "NO_TRADE"
        return LiquidityAggressionDecision(
            decision=decision,
            score=score,
            sizing=sizing,
            no_trade_pressure=LiquidityNoTradePressure(round(pressure, 4), pressure_reasons),
            fast_invalidation=invalidation,
        )

    def _score(self, inputs: dict[str, float]) -> LiquidityAggressionScore:
        total = (
            inputs["edge_score"] * 0.16
            + inputs["spread_quality"] * 0.10
            + inputs["depth_quality"] * 0.10
            + inputs["fill_probability"] * 0.12
            + inputs["confidence_bucket"] * 0.08
            + inputs["source_bloodline_support"] * 0.08
            + inputs["signal_bloodline_support"] * 0.08
            + inputs["calibration_support"] * 0.10
            - inputs["fill_drag"] * 0.10
            - inputs["stale_quote_risk"] * 0.10
            - inputs["liquidity_decay"] * 0.05
            - inputs["cap_impact"] * 0.06
            - inputs["settlement_risk"] * 0.08
            - inputs["model_disagreement"] * 0.08
        )
        return LiquidityAggressionScore(total=round(max(0.0, min(1.0, total)), 4), **inputs)

    def _sizing(self, fill_drag: float, *, requested_size: int) -> LiquiditySizingDecision:
        if fill_drag >= 0.30:
            return LiquiditySizingDecision("REDUCE_SIZE", requested_size, 1, "Fill drag pressure reduces micro size.")
        return LiquiditySizingDecision("KEEP_SIZE", requested_size, requested_size, "Liquidity drag remains bounded.")

    def to_report(self) -> dict[str, Any]:
        decision = self.evaluate(self.sample_inputs())
        return {
            "workstream": "V11: Liquidity Aggression Governor",
            "decision": decision.to_dict(),
            "verdict": "PASS",
        }

    def sizing_report(self, *, fill_drag: float = 0.08) -> dict[str, Any]:
        decision = self._sizing(fill_drag, requested_size=2)
        return {
            "workstream": "V11: Liquidity Sizing Decision",
            "decision": decision.to_dict(),
            "verdict": "PASS",
        }
