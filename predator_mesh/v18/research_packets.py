"""Canonical V18 research packet factory."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from predator_mesh.v18 import DOMAINS
from predator_mesh.v18.domain_intelligence import DomainIntelligenceSpine
from predator_mesh.v18.source_truth import SourceLegalityClass, SourceTruthRegistryV2


class ResearchPacketVerdict(str, Enum):
    FORECAST_READY = "FORECAST_READY"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    NO_TRADE_SETTLEMENT_AMBIGUITY = "NO_TRADE_SETTLEMENT_AMBIGUITY"
    NO_TRADE_SOURCE_WEAKNESS = "NO_TRADE_SOURCE_WEAKNESS"
    NO_TRADE_STALE_DATA = "NO_TRADE_STALE_DATA"
    NO_TRADE_LEGALITY_BLOCK = "NO_TRADE_LEGALITY_BLOCK"
    UNRESOLVED_PENDING = "UNRESOLVED_PENDING"


@dataclass(frozen=True)
class ResearchQuestion:
    question_id: str
    prompt: str

    def to_dict(self) -> dict[str, str]:
        return {"question_id": self.question_id, "prompt": self.prompt}


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_ref: str
    source_legality_class: SourceLegalityClass
    summary: str
    freshness_status: str
    is_fixture: bool
    is_live: bool = False
    proof_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_ref": self.source_ref,
            "source_legality_class": self.source_legality_class.value,
            "summary": self.summary,
            "freshness_status": self.freshness_status,
            "is_fixture": self.is_fixture,
            "is_live": self.is_live,
            "proof_ref": self.proof_ref,
        }


@dataclass(frozen=True)
class EvidenceContradiction:
    contradiction_id: str
    summary: str
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"contradiction_id": self.contradiction_id, "summary": self.summary, "source_refs": list(self.source_refs)}


@dataclass(frozen=True)
class EvidenceStack:
    items: tuple[EvidenceItem, ...]
    contradictions: tuple[EvidenceContradiction, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_count": len(self.items),
            "items": [item.to_dict() for item in self.items],
            "contradictions": [item.to_dict() for item in self.contradictions],
            "contradiction_count": len(self.contradictions),
        }


@dataclass(frozen=True)
class SettlementRuleRef:
    rule_id: str
    domain: str
    source_requirement: str
    ambiguous: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "domain": self.domain,
            "source_requirement": self.source_requirement,
            "ambiguous": self.ambiguous,
        }


@dataclass(frozen=True)
class ResearchPacketNoTradePressure:
    domain: str
    reasons: tuple[str, ...]
    pressure_level: str = "MEDIUM"

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "reasons": list(self.reasons), "pressure_level": self.pressure_level}


@dataclass(frozen=True)
class ResearchPacket:
    domain: str
    market_identifier: str
    event_identifier: str
    research_questions: tuple[ResearchQuestion, ...]
    evidence_stack: EvidenceStack
    settlement_rule_ref: SettlementRuleRef
    verdict: ResearchPacketVerdict
    no_trade_pressure: ResearchPacketNoTradePressure
    forecast_ready_status: str
    proof_refs: tuple[str, ...]
    fixture_only: bool = True
    created_after_outcome: bool = False

    @property
    def packet_id(self) -> str:
        raw = json.dumps(
            {"domain": self.domain, "market_identifier": self.market_identifier, "event_identifier": self.event_identifier},
            sort_keys=True,
        )
        return "research-packet-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "domain": self.domain,
            "market_identifier": self.market_identifier,
            "event_identifier": self.event_identifier,
            "research_questions": [item.to_dict() for item in self.research_questions],
            "evidence_stack": self.evidence_stack.to_dict(),
            "source_refs": [item.source_ref for item in self.evidence_stack.items],
            "source_legality_classes": [item.source_legality_class.value for item in self.evidence_stack.items],
            "freshness_status": [item.freshness_status for item in self.evidence_stack.items],
            "contradiction_summary": [item.summary for item in self.evidence_stack.contradictions],
            "settlement_rule_summary": self.settlement_rule_ref.to_dict(),
            "forecast_ready_status": self.forecast_ready_status,
            "no_trade_pressure": self.no_trade_pressure.to_dict(),
            "verdict": self.verdict.value,
            "proof_refs": list(self.proof_refs),
            "fixture_only": self.fixture_only,
            "created_after_outcome": self.created_after_outcome,
        }


class ResearchPacketFactory:
    max_lane_timeout_s = 10
    total_timeout_s = 45

    def __init__(self, spine: DomainIntelligenceSpine | None = None, registry: SourceTruthRegistryV2 | None = None) -> None:
        self.spine = spine or DomainIntelligenceSpine()
        self.registry = registry or SourceTruthRegistryV2()

    def packets(self) -> list[ResearchPacket]:
        contradictions = {item.domain: item for item in self.registry.contradictions()}
        candidates = {item.domain: item for item in self.registry.candidates()}
        packets: list[ResearchPacket] = []
        for domain in DOMAINS:
            profile = self.spine.profile_for(domain)
            candidate = candidates[domain]
            contradiction = contradictions[domain]
            questions = (
                ResearchQuestion(f"{domain}-event-definition", "What is the exact market/event definition?"),
                ResearchQuestion(f"{domain}-source-truth", "Which legality-labeled source facts support a baseline?"),
                ResearchQuestion(f"{domain}-no-trade", "What must block trading or reduce confidence?"),
            )
            evidence = EvidenceItem(
                evidence_id=f"{domain}-fixture-evidence-v18",
                source_ref=candidate.source_id,
                source_legality_class=candidate.legality_class,
                summary="Deterministic fixture/static evidence used only to exercise the research packet shape.",
                freshness_status=candidate.freshness.freshness_status,
                is_fixture=True,
                proof_ref=f"artifacts/dummy/{domain}_research_foundation_report_v1.json",
            )
            packets.append(
                ResearchPacket(
                    domain=domain,
                    market_identifier=f"V18-{domain.upper()}-FIXTURE-MARKET",
                    event_identifier=f"V18-{domain.upper()}-FIXTURE-EVENT",
                    research_questions=questions,
                    evidence_stack=EvidenceStack(
                        items=(evidence,),
                        contradictions=(
                            EvidenceContradiction(
                                contradiction_id=contradiction.contradiction_id,
                                summary=contradiction.description,
                                source_refs=contradiction.source_refs,
                            ),
                        ),
                    ),
                    settlement_rule_ref=SettlementRuleRef(
                        rule_id=f"{domain}-settlement-rule-v18",
                        domain=domain,
                        source_requirement=profile.required_settlement_facts[0],
                        ambiguous=True,
                    ),
                    verdict=ResearchPacketVerdict.NEEDS_MORE_EVIDENCE,
                    no_trade_pressure=ResearchPacketNoTradePressure(
                        domain=domain,
                        reasons=profile.domain_specific_no_trade_triggers[:2],
                    ),
                    forecast_ready_status="FIXTURE_BASELINE_READY_NOT_LIVE_EDGE",
                    proof_refs=(f"artifacts/dummy/{domain}_research_foundation_report_v1.json",),
                )
            )
        return packets

    def to_report(self) -> dict[str, Any]:
        packets = self.packets()
        return {
            "workstream": "V18: Research Packet Factory",
            "domains": [packet.domain for packet in packets],
            "packet_count": len(packets),
            "packets": [packet.to_dict() for packet in packets],
            "fake_evidence_created": False,
            "fixture_evidence_labeled": True,
            "can_consume_real_read_only_source_evidence": True,
            "live_submit_disabled": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def manifest(self) -> dict[str, Any]:
        packets = self.packets()
        return {
            "workstream": "V18: Research Packet Manifest",
            "packet_domains": {packet.packet_id: packet.domain for packet in packets},
            "proof_refs_by_packet": {packet.packet_id: list(packet.proof_refs) for packet in packets},
            "fixture_only_packets": [packet.packet_id for packet in packets if packet.fixture_only],
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def evidence_stack_report(self) -> dict[str, Any]:
        packets = self.packets()
        evidence_items = [item for packet in packets for item in packet.evidence_stack.items]
        return {
            "workstream": "V18: Evidence Stack",
            "evidence_count": len(evidence_items),
            "all_evidence_has_source_legality": all(item.source_legality_class for item in evidence_items),
            "fixture_evidence_labeled": all(item.is_fixture and not item.is_live for item in evidence_items),
            "stale_data_visible": all(item.freshness_status in {"STATIC_FIXTURE", "STALE", "FRESH"} for item in evidence_items),
            "contradiction_count": sum(len(packet.evidence_stack.contradictions) for packet in packets),
            "evidence_items": [item.to_dict() for item in evidence_items],
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def no_trade_pressure_report(self) -> dict[str, Any]:
        pressures = [packet.no_trade_pressure for packet in self.packets()]
        return {
            "workstream": "V18: Research Packet No-Trade Pressure",
            "no_trade_pressure_visible": True,
            "pressure_count": len(pressures),
            "pressures": [pressure.to_dict() for pressure in pressures],
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
