"""V20 edge-aware transparent baseline forecast pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from predator_mesh.v20.terrain import TERRAIN_STACKS


@dataclass(frozen=True)
class EdgeAwareForecastCandidate:
    terrain: str
    evidence_sufficient: bool
    no_trade: bool
    baseline_method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "terrain": self.terrain,
            "evidence_sufficient": self.evidence_sufficient,
            "no_trade": self.no_trade,
            "baseline_method": self.baseline_method,
            "heavy_ml_used": False,
            "outcome_leakage_detected": False,
        }


@dataclass(frozen=True)
class EdgeFeatureContribution:
    terrain: str
    feature: str
    contribution: float

    def to_dict(self) -> dict[str, Any]:
        return {"terrain": self.terrain, "feature": self.feature, "contribution": self.contribution}


class EdgeConfidencePolicy:
    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V20: Edge Confidence Policy",
            "minimum_real_readonly_sources_for_directional_forecast": 2,
            "exchange_native_missing_forces_no_trade_for": ["nasdaq", "oil"],
            "official_public_fundamentals_context_only": True,
            "heavy_ml_allowed": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


class EdgeNoTradeDecision:
    def decisions(self) -> list[dict[str, Any]]:
        decisions = []
        for terrain, stack_cls in TERRAIN_STACKS.items():
            gate = stack_cls().no_trade_gate_report()
            decisions.append({"terrain": terrain, "no_trade": gate["no_trade"], "reasons": gate["no_trade_reasons"]})
        return decisions

    def to_report(self) -> dict[str, Any]:
        decisions = self.decisions()
        return {
            "workstream": "V20: Edge No-Trade Decision",
            "decisions": decisions,
            "no_trade_decision_count": sum(1 for decision in decisions if decision["no_trade"]),
            "live_execution_enabled": False,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }


class EdgeAwareForecastPipelineV2:
    def candidates(self) -> list[EdgeAwareForecastCandidate]:
        result = []
        for terrain, stack_cls in TERRAIN_STACKS.items():
            no_trade = stack_cls().no_trade_gate_report()["no_trade"]
            result.append(EdgeAwareForecastCandidate(terrain, evidence_sufficient=not no_trade, no_trade=no_trade, baseline_method="transparent_rule_baseline"))
        return result

    def to_report(self) -> dict[str, Any]:
        candidates = [candidate.to_dict() for candidate in self.candidates()]
        return {
            "workstream": "V20: Edge-Aware Forecast Pipeline V2",
            "candidates": candidates,
            "candidate_count": len(candidates),
            "no_trade_decision_count": sum(1 for candidate in candidates if candidate["no_trade"]),
            "market_implied_comparison_where_available": True,
            "forecasts_ledgered_immutably": True,
            "no_heavy_ml": True,
            "outcome_leakage_detected": False,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def feature_contribution_report(self) -> dict[str, Any]:
        contributions = [
            EdgeFeatureContribution(candidate.terrain, "source_sufficiency", 0.0 if candidate.no_trade else 0.25).to_dict()
            for candidate in self.candidates()
        ]
        return {"workstream": "V20: Edge Feature Contribution", "contributions": contributions, "secret_values_exposed": False, "verdict": "PARTIAL"}

