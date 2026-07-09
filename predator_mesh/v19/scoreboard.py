"""Domain scoreboard V2 and activation matrix for V19."""

from __future__ import annotations

from typing import Any

from predator_mesh.v19 import DOMAINS
from predator_mesh.v19.compounding import AutonomousCompoundingEngine
from predator_mesh.v19.source_activation import RealReadOnlySourceActivationController


class DomainScoreboardV2:
    def scores(self) -> list[dict[str, Any]]:
        modes = RealReadOnlySourceActivationController().to_report()["activation_modes_by_domain"]
        proposal_count = len(AutonomousCompoundingEngine().proposals())
        return [
            {
                "domain": domain,
                "source_activation_mode": modes[domain],
                "real_evidence_count": 0,
                "fixture_evidence_count": 1,
                "blocked_source_count": 1,
                "legality_blockers": [],
                "freshness_state": "STATIC_FIXTURE",
                "contradiction_count": 1,
                "research_packet_count": 1,
                "forecast_activation_count": 1,
                "no_trade_count": 1,
                "outcome_observer_mode": "UNRESOLVED_PENDING",
                "unresolved_outcome_count": 1,
                "calibration_sample_count": 0,
                "compounding_proposal_count": proposal_count,
                "readiness_score": 0.35,
                "next_action": "Promote a bounded public read-only source after operator approval and proof.",
            }
            for domain in DOMAINS
        ]

    def to_report(self) -> dict[str, Any]:
        scores = self.scores()
        return {
            "workstream": "V19: Domain Scoreboard V2",
            "domains": [item["domain"] for item in scores],
            "scores": scores,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def activation_matrix_report(self) -> dict[str, Any]:
        scores = self.scores()
        return {
            "workstream": "V19: Domain Activation Matrix",
            "matrix": scores,
            "real_evidence_count": sum(item["real_evidence_count"] for item in scores),
            "fixture_evidence_count": sum(item["fixture_evidence_count"] for item in scores),
            "blocked_source_count": sum(item["blocked_source_count"] for item in scores),
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }
