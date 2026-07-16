"""V20 mission state v6."""

from __future__ import annotations

from typing import Any

from predator_mesh.v20.approval_gates import SourceApprovalGateV2, SourceLicenseGate
from predator_mesh.v20.compounding import AutonomousCompoundingControlPlaneV3
from predator_mesh.v20.forecast_pipeline import EdgeAwareForecastPipelineV2
from predator_mesh.v20.github_source_miner import GitHubSourceMiner
from predator_mesh.v20.official_adapters import OfficialPublicAdapterActivationPack
from predator_mesh.v20.recommendations import SourceGapRecommendationEngine
from predator_mesh.v20.scoreboard import DomainScoreboardV4
from predator_mesh.v20.source_universe import SourceUniverse
from predator_mesh.v20.terrain import CryptoDirectionTerrainStack, NasdaqDirectionTerrainStack, OilDirectionTerrainStack, SportsEdgeTerrainStack, WeatherEdgeTerrainStack


class DummyMissionStateV6:
    def to_report(self) -> dict[str, Any]:
        source_universe = SourceUniverse().to_report()
        github = GitHubSourceMiner().mine().to_report()
        approval = SourceApprovalGateV2().to_report()
        official = OfficialPublicAdapterActivationPack().to_report()
        recommendations = SourceGapRecommendationEngine().to_report()
        scoreboard = DomainScoreboardV4().to_report()
        return {
            "workstream": "V20: Dummy Mission State V6",
            "v17_truth_loop_status": "PASS",
            "v18_domain_foundation_status": "PARTIAL",
            "v19_activation_architecture_status": "PARTIAL",
            "source_universe_status": source_universe["verdict"],
            "github_miner_status": github["verdict"],
            "github_miner_mode": github["mode"],
            "approved_source_gate_status": approval["verdict"],
            "official_public_adapter_activation_status": official["verdict"],
            "commercial_licensed_gate_status": SourceLicenseGate().to_report()["verdict"],
            "nasdaq_direction_terrain_status": NasdaqDirectionTerrainStack().to_report()["verdict"],
            "oil_direction_terrain_status": OilDirectionTerrainStack().to_report()["verdict"],
            "crypto_direction_terrain_status": CryptoDirectionTerrainStack().to_report()["verdict"],
            "weather_terrain_status": WeatherEdgeTerrainStack().to_report()["verdict"],
            "sports_terrain_status": SportsEdgeTerrainStack().to_report()["verdict"],
            "forecast_pipeline_v2_status": EdgeAwareForecastPipelineV2().to_report()["verdict"],
            "source_gap_recommendation_status": recommendations["verdict"],
            "highest_priority_missing_source_gaps": recommendations["highest_priority_missing_source_gaps"],
            "compounding_control_plane_v3_status": AutonomousCompoundingControlPlaneV3().to_report()["verdict"],
            "domain_scoreboard_v4_status": scoreboard["verdict"],
            "real_vs_fixture_split": {"real_read_only": 0, "fixture_static": scoreboard["fixture_total"]},
            "live_submit_disabled": True,
            "caps_unchanged": True,
            "top_blockers": ["CME NQ/ES futures orderbook license", "CME CL / ICE Brent futures license", "EIA_API_KEY missing", "Cboe options/skew license"],
            "next_bundle_recommendation": "Promote one bounded official/public adapter with proof, then request operator decision on CME/ICE/Databento source acquisition.",
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }
