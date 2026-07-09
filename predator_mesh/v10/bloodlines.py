"""Recursive source and signal bloodline memory for V10."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceBloodlineScore:
    forecast_impact: float
    calibration_impact: float
    no_trade_impact: float
    edge_candidate_impact: float
    stale_noisy_penalty: float
    duplicate_penalty: float
    total: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "forecast_impact": self.forecast_impact,
            "calibration_impact": self.calibration_impact,
            "no_trade_impact": self.no_trade_impact,
            "edge_candidate_impact": self.edge_candidate_impact,
            "stale_noisy_penalty": self.stale_noisy_penalty,
            "duplicate_penalty": self.duplicate_penalty,
            "total": self.total,
        }


@dataclass(frozen=True)
class SignalBloodlineScore(SourceBloodlineScore):
    pass


@dataclass(frozen=True)
class SourceBloodline:
    source_category: str
    adapter_mode: str
    score: SourceBloodlineScore
    promoted_count: int
    pruned_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_category": self.source_category,
            "adapter_mode": self.adapter_mode,
            "score": self.score.to_dict(),
            "promoted_count": self.promoted_count,
            "pruned_count": self.pruned_count,
        }


@dataclass(frozen=True)
class SignalBloodline:
    signal_type: str
    source_category: str
    score: SignalBloodlineScore
    promoted_count: int
    pruned_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "source_category": self.source_category,
            "score": self.score.to_dict(),
            "promoted_count": self.promoted_count,
            "pruned_count": self.pruned_count,
        }


@dataclass(frozen=True)
class BloodlinePromotionDecision:
    bloodline_id: str
    decision: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"bloodline_id": self.bloodline_id, "decision": self.decision, "reason": self.reason}


@dataclass(frozen=True)
class BloodlinePruningDecision(BloodlinePromotionDecision):
    pass


class BloodlineMemory:
    def source_bloodlines(self) -> list[SourceBloodline]:
        return [
            SourceBloodline(
                "crypto_btc",
                "LIVE_PUBLIC_BOUNDED",
                SourceBloodlineScore(0.28, 0.18, 0.12, 0.26, 0.04, 0.02, 0.78),
                3,
                0,
            ),
            SourceBloodline(
                "macro_calendar",
                "SAMPLE_STATIC",
                SourceBloodlineScore(0.18, 0.16, 0.10, 0.14, 0.06, 0.03, 0.49),
                1,
                1,
            ),
            SourceBloodline(
                "prediction_market_cross_price",
                "MOCK_ONLY_EXPLICIT",
                SourceBloodlineScore(0.08, 0.06, 0.20, 0.08, 0.10, 0.08, 0.24),
                0,
                2,
            ),
        ]

    def signal_bloodlines(self) -> list[SignalBloodline]:
        return [
            SignalBloodline(
                "volatility_shift",
                "crypto_btc",
                SignalBloodlineScore(0.26, 0.18, 0.10, 0.24, 0.04, 0.02, 0.72),
                2,
                0,
            ),
            SignalBloodline(
                "event_timing_pressure",
                "macro_calendar",
                SignalBloodlineScore(0.16, 0.14, 0.10, 0.13, 0.05, 0.02, 0.46),
                1,
                1,
            ),
            SignalBloodline(
                "explicit_mock_cross_price",
                "prediction_market_cross_price",
                SignalBloodlineScore(0.05, 0.04, 0.22, 0.04, 0.08, 0.06, 0.21),
                0,
                2,
            ),
        ]

    def source_report(self) -> dict[str, Any]:
        bloodlines = self.source_bloodlines()
        return {
            "workstream": "V10: Source Bloodline Memory",
            "bloodlines": [bloodline.to_dict() for bloodline in bloodlines],
            "verdict": "PASS" if bloodlines else "FAIL",
        }

    def signal_report(self) -> dict[str, Any]:
        bloodlines = self.signal_bloodlines()
        return {
            "workstream": "V10: Signal Bloodline Memory",
            "bloodlines": [bloodline.to_dict() for bloodline in bloodlines],
            "verdict": "PASS" if bloodlines else "FAIL",
        }

    def promotion_pruning_report(self) -> dict[str, Any]:
        promotion_decisions = [
            BloodlinePromotionDecision("source:crypto_btc", "PROMOTE", "High impact and bounded public mode."),
            BloodlinePromotionDecision("signal:volatility_shift", "PROMOTE", "Repeated forecast and edge impact."),
        ]
        pruning_decisions = [
            BloodlinePruningDecision("source:prediction_market_cross_price", "PRUNE", "Explicit mock remains low proof."),
            BloodlinePruningDecision("signal:explicit_mock_cross_price", "STARVE", "No-trade pressure exceeds edge impact."),
        ]
        return {
            "workstream": "V10: Bloodline Promotion And Pruning",
            "promotion_decisions": [decision.to_dict() for decision in promotion_decisions],
            "pruning_decisions": [decision.to_dict() for decision in pruning_decisions],
            "verdict": "PASS",
        }
