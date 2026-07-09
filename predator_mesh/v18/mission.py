"""V18 domain scoreboard and mission-state summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from predator_mesh.v18 import DOMAINS
from predator_mesh.v18.domain_baselines import DomainBaselineForecastEngineV2
from predator_mesh.v18.research_packets import ResearchPacketFactory
from predator_mesh.v18.source_truth import SourceTruthRegistryV2


@dataclass(frozen=True)
class DomainBlocker:
    domain: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"domain": self.domain, "reason": self.reason}


@dataclass(frozen=True)
class DomainNextAction:
    domain: str
    action: str

    def to_dict(self) -> dict[str, str]:
        return {"domain": self.domain, "action": self.action}


@dataclass(frozen=True)
class DomainReadinessScore:
    domain: str
    source_coverage: str
    source_legality_status: str
    research_packet_status: str
    baseline_forecast_status: str
    settlement_mapping_status: str
    no_trade_gate_status: str
    ledger_integration_status: str
    calibration_sample_count: int
    unresolved_outcome_count: int
    current_blocker: DomainBlocker
    next_action: DomainNextAction
    evidence_state: str = "FIXTURE_STATIC"

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "source_coverage": self.source_coverage,
            "source_legality_status": self.source_legality_status,
            "research_packet_status": self.research_packet_status,
            "baseline_forecast_status": self.baseline_forecast_status,
            "settlement_mapping_status": self.settlement_mapping_status,
            "no_trade_gate_status": self.no_trade_gate_status,
            "ledger_integration_status": self.ledger_integration_status,
            "calibration_sample_count": self.calibration_sample_count,
            "unresolved_outcome_count": self.unresolved_outcome_count,
            "current_blocker": self.current_blocker.to_dict(),
            "next_action": self.next_action.to_dict(),
            "evidence_state": self.evidence_state,
        }


class DomainMissionScoreboard:
    def scores(self) -> list[DomainReadinessScore]:
        return [
            DomainReadinessScore(
                domain=domain,
                source_coverage="FIXTURE_STATIC",
                source_legality_status="PUBLIC_STATIC_FIXTURE",
                research_packet_status="PACKET_CREATED",
                baseline_forecast_status="FIXTURE_BASELINE_LEDGERED",
                settlement_mapping_status="FIXTURE_PROFILE_CREATED",
                no_trade_gate_status="ACTIVE_FOR_AMBIGUITY_AND_SOURCE_WEAKNESS",
                ledger_integration_status="INTEGRATED_WITH_V17_LEDGER_SHAPES",
                calibration_sample_count=0,
                unresolved_outcome_count=1,
                current_blocker=DomainBlocker(domain, "Approved live public read-only source not promoted yet."),
                next_action=DomainNextAction(domain, "Collect legality-approved read-only evidence and wait for outcomes before promotion."),
            )
            for domain in DOMAINS
        ]

    def to_report(self) -> dict[str, Any]:
        scores = self.scores()
        return {
            "workstream": "V18: Domain Mission Scoreboard",
            "domains": [score.domain for score in scores],
            "scores": [score.to_dict() for score in scores],
            "fixture_domain_count": sum(1 for score in scores if score.evidence_state == "FIXTURE_STATIC"),
            "real_readonly_domain_count": sum(1 for score in scores if score.evidence_state == "REAL_READ_ONLY"),
            "blocked_domain_count": sum(1 for score in scores if score.evidence_state == "BLOCKED"),
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }


class DummyMissionStateV18:
    def to_report(self) -> dict[str, Any]:
        packets = ResearchPacketFactory().packets()
        snapshots = DomainBaselineForecastEngineV2().snapshots()
        scoreboard = DomainMissionScoreboard().to_report()
        registry = SourceTruthRegistryV2().to_report()
        fixture_evidence_count = sum(1 for packet in packets if packet.fixture_only)
        real_evidence_count = sum(1 for snapshot in snapshots if snapshot.real_evidence)
        return {
            "workstream": "V18: Dummy Mission State",
            "mission_state_verdict": "PARTIAL_FIXTURE_STATIC_SOURCES",
            "v16_carried_state": "PARTIAL_NO_ELIGIBLE_MARKET_OR_EXTERNAL_UNKNOWN",
            "v17_truth_loop_status": "PASS_OR_UNKNOWN_FROM_ARTIFACT",
            "domain_intelligence_status": "PASS",
            "research_packet_count": len(packets),
            "baseline_forecast_count": len(snapshots),
            "source_truth_registry_status": registry["verdict"],
            "settlement_mapper_status": "PASS",
            "domain_scoreboard": scoreboard,
            "ledger_integration_status": "PASS",
            "fixture_evidence_count": fixture_evidence_count,
            "real_evidence_count": real_evidence_count,
            "fixture_vs_real_evidence_split": {"fixture_static": fixture_evidence_count, "real_read_only": real_evidence_count},
            "current_blocker": "All V18 domain packets are fixture/static until approved live public read-only sources produce outcome-backed proof.",
            "next_action": "Promote only legality-approved read-only source bloodlines after outcomes accumulate.",
            "live_submit_disabled": True,
            "caps_unchanged": True,
            "no_direct_order_cancel_bypass": True,
            "fixture_evidence_claimed_real": False,
            "secrets_exposed": False,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }
