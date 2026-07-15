"""Point-in-time, settlement-verified inputs for external evolution evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from dummy.genome import ForecastGenome, GenomeMutationProposal, GenomeValidationError


def _utc(value: datetime | str) -> datetime:
    try:
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
    except ValueError as exc:
        raise GenomeValidationError("evaluation timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GenomeValidationError("evaluation timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _probability(value: float, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise GenomeValidationError(f"{name} must be in [0, 1]")
    return parsed


@dataclass(frozen=True, slots=True)
class EvolutionEvaluationCase:
    case_id: str
    event_cluster_id: str
    decision_at: datetime
    market_close_at: datetime
    settlement_received_at: datetime
    candidate_probability: float
    incumbent_probability: float
    market_prior_probability: float
    result_yes: bool
    transfer_group: str
    regime: str
    settlement_verified: bool
    point_in_time_verified: bool
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("case_id", "event_cluster_id", "transfer_group", "regime"):
            if not getattr(self, field_name).strip():
                raise GenomeValidationError(f"{field_name} is required")
        decision = _utc(self.decision_at)
        close = _utc(self.market_close_at)
        settlement = _utc(self.settlement_received_at)
        if not decision <= close <= settlement:
            raise GenomeValidationError("evaluation case violates causal time")
        if self.settlement_verified is not True or self.point_in_time_verified is not True:
            raise GenomeValidationError(
                "evolution evaluation requires verified point-in-time settlement evidence"
            )
        if type(self.result_yes) is not bool:
            raise GenomeValidationError("evaluation outcome must be boolean")
        evidence = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if not evidence or any(not item for item in evidence):
            raise GenomeValidationError("evaluation case evidence is required")
        if len(set(evidence)) != len(evidence):
            raise GenomeValidationError("evaluation case evidence is duplicated")
        object.__setattr__(self, "decision_at", decision)
        object.__setattr__(self, "market_close_at", close)
        object.__setattr__(self, "settlement_received_at", settlement)
        for field_name in (
            "candidate_probability",
            "incumbent_probability",
            "market_prior_probability",
        ):
            object.__setattr__(
                self,
                field_name,
                _probability(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "evidence_ids", evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "event_cluster_id": self.event_cluster_id,
            "decision_at": self.decision_at.isoformat().replace("+00:00", "Z"),
            "market_close_at": self.market_close_at.isoformat().replace("+00:00", "Z"),
            "settlement_received_at": self.settlement_received_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "candidate_probability": self.candidate_probability,
            "incumbent_probability": self.incumbent_probability,
            "market_prior_probability": self.market_prior_probability,
            "result_yes": self.result_yes,
            "transfer_group": self.transfer_group,
            "regime": self.regime,
            "settlement_verified": self.settlement_verified,
            "point_in_time_verified": self.point_in_time_verified,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EvolutionEvaluationCase:
        return cls(
            case_id=str(data["case_id"]),
            event_cluster_id=str(data["event_cluster_id"]),
            decision_at=_utc(data["decision_at"]),
            market_close_at=_utc(data["market_close_at"]),
            settlement_received_at=_utc(data["settlement_received_at"]),
            candidate_probability=float(data["candidate_probability"]),
            incumbent_probability=float(data["incumbent_probability"]),
            market_prior_probability=float(data["market_prior_probability"]),
            result_yes=data["result_yes"],
            transfer_group=str(data["transfer_group"]),
            regime=str(data["regime"]),
            settlement_verified=data.get("settlement_verified") is True,
            point_in_time_verified=data.get("point_in_time_verified") is True,
            evidence_ids=tuple(data.get("evidence_ids", ())),
        )


@dataclass(frozen=True, slots=True)
class CandidateEvaluationInput:
    candidate: ForecastGenome
    mutation_proposal: GenomeMutationProposal
    incumbent_id: str
    market_prior_id: str
    primary_transfer_group: str
    training_event_cluster_ids: tuple[str, ...]
    candidate_selection_evidence_ids: tuple[str, ...]
    held_out_cases: tuple[EvolutionEvaluationCase, ...]
    deterministic_replay_verified: bool
    replay_report_id: str
    governance_preserved: bool
    governance_report_id: str

    def __post_init__(self) -> None:
        if self.mutation_proposal.candidate_genome != self.candidate:
            raise GenomeValidationError("candidate does not match mutation proposal")
        if not self.mutation_proposal.allowed_by_constitution:
            raise GenomeValidationError("constitution-blocked candidate cannot be evaluated")
        for field_name in (
            "incumbent_id",
            "market_prior_id",
            "primary_transfer_group",
            "replay_report_id",
            "governance_report_id",
        ):
            if not getattr(self, field_name).strip():
                raise GenomeValidationError(f"{field_name} is required")
        if len({self.candidate.genome_id, self.incumbent_id, self.market_prior_id}) != 3:
            raise GenomeValidationError("candidate and baselines must be distinct")
        training = tuple(sorted(str(item).strip() for item in self.training_event_cluster_ids))
        selection = tuple(
            sorted(str(item).strip() for item in self.candidate_selection_evidence_ids)
        )
        cases = tuple(sorted(self.held_out_cases, key=lambda item: item.case_id))
        if not training or not selection or not cases:
            raise GenomeValidationError(
                "candidate selection and held-out evidence must be non-empty"
            )
        if any(not item for item in (*training, *selection)):
            raise GenomeValidationError("candidate evidence identifiers cannot be blank")
        if len(set(training)) != len(training) or len(set(selection)) != len(selection):
            raise GenomeValidationError("candidate evidence identifiers are duplicated")
        case_ids = tuple(item.case_id for item in cases)
        if len(set(case_ids)) != len(case_ids):
            raise GenomeValidationError("held-out case IDs are duplicated")
        heldout_clusters = {item.event_cluster_id for item in cases}
        if heldout_clusters.intersection(training):
            raise GenomeValidationError("held-out event cluster entered candidate training")
        heldout_evidence = {item for case in cases for item in case.evidence_ids}
        if heldout_evidence.intersection(selection):
            raise GenomeValidationError("held-out evidence entered candidate selection")
        object.__setattr__(self, "training_event_cluster_ids", training)
        object.__setattr__(self, "candidate_selection_evidence_ids", selection)
        object.__setattr__(self, "held_out_cases", cases)


__all__ = ["CandidateEvaluationInput", "EvolutionEvaluationCase"]
