"""V20 domain scoreboard."""

from __future__ import annotations

from typing import Any

from predator_mesh.v20.recommendations import SourceGapRecommendationEngine
from predator_mesh.v20.source_universe import SourceTier, SourceUniverse
from predator_mesh.v20.terrain import TERRAIN_STACKS


class DomainScoreboardV4:
    def rows(self) -> list[dict[str, Any]]:
        universe = SourceUniverse()
        recommendations = SourceGapRecommendationEngine().priorities()
        rows = []
        for terrain, stack_cls in TERRAIN_STACKS.items():
            stack = stack_cls()
            terrain_report = stack.to_report()
            domain_candidates = [candidate for candidate in universe.candidates() if terrain.split("_")[0] in " ".join(candidate.domains) or terrain in " ".join(candidate.domains)]
            row = {
                "terrain": terrain,
                "source_universe_coverage": len(domain_candidates),
                "tier_0_coverage": sum(1 for candidate in domain_candidates if candidate.tier == SourceTier.TIER_0_EXCHANGE_NATIVE),
                "tier_1_coverage": sum(1 for candidate in domain_candidates if candidate.tier == SourceTier.TIER_1_OFFICIAL_PUBLIC),
                "tier_2_gate_status": "BLOCKED_LICENSE_REQUIRED",
                "tier_3_github_adapter_candidate_count": sum(1 for candidate in domain_candidates if candidate.tier == SourceTier.TIER_3_OPEN_SOURCE_GITHUB),
                "real_readonly_active_count": 0,
                "fixture_count": 1,
                "blocker_count": len(terrain_report["required_source_needs"]) if terrain_report["exchange_native_missing"] else 1,
                "source_gap_priority": next((item.expected_edge_impact for item in recommendations if terrain.split("_")[0] in item.domain or terrain.split("_")[0] in item.source.lower()), 70),
                "evidence_sufficiency": "INSUFFICIENT_REAL_EDGE_EVIDENCE",
                "forecast_readiness": "NO_TRADE",
                "no_trade_pressure": "HIGH",
                "outcome_observer_readiness": "PLAN_ONLY",
                "calibration_readiness": "PENDING_REAL_EVIDENCE",
                "next_source_acquisition_recommendation": SourceGapRecommendationEngine().priorities()[0].source if terrain == "nasdaq" else SourceGapRecommendationEngine().priorities()[1].source if terrain == "oil" else "promote bounded official/public adapter",
            }
            rows.append(row)
        return rows

    def to_report(self) -> dict[str, Any]:
        rows = self.rows()
        return {
            "workstream": "V20: Domain Scoreboard V4",
            "rows": rows,
            "real_readonly_active_total": sum(row["real_readonly_active_count"] for row in rows),
            "fixture_total": sum(row["fixture_count"] for row in rows),
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def coverage_scoreboard_report(self) -> dict[str, Any]:
        rows = self.rows()
        return {"workstream": "V20: Source Universe Coverage Scoreboard", "coverage": rows, "secret_values_exposed": False, "verdict": "PARTIAL"}

    def readiness_scoreboard_report(self) -> dict[str, Any]:
        rows = [
            {
                "terrain": row["terrain"],
                "evidence_sufficiency": row["evidence_sufficiency"],
                "forecast_readiness": row["forecast_readiness"],
                "no_trade_pressure": row["no_trade_pressure"],
            }
            for row in self.rows()
        ]
        return {"workstream": "V20: Edge Terrain Readiness Scoreboard", "readiness": rows, "secret_values_exposed": False, "verdict": "PARTIAL"}
