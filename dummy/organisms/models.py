"""Immutable inputs and artifacts for deterministic forecast organisms."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from dummy import VNEXT_MATURITY
from dummy.agents import AgentVertical
from dummy.chronos import ClockDomain


_EPISODE_NAMESPACE = uuid.UUID("c450093d-2629-59d5-8bce-c4393c491183")

CAPABILITY_STEP_NAMES = (
    "valid_market_detected",
    "market_prior_frozen",
    "world_model_built",
    "deterministic_organism_instantiated",
    "point_in_time_evidence_gathered",
    "competing_futures_generated",
    "adversarial_attacks_executed",
    "decomposed_confidence_calculated",
    "knowledge_boundaries_estimated",
    "additional_analysis_value_decided",
    "forecast_or_abstention_produced",
    "decision_state_frozen",
    "realistic_execution_simulated",
    "verified_reality_settled",
    "participating_agents_graded",
    "calibration_and_trust_update_proposed",
    "full_episode_stored",
    "bounded_improvements_proposed",
    "improvements_replayed_on_held_out_evidence",
    "promotion_candidates_presented_without_authority_change",
)


class EpisodeValidationError(ValueError):
    """An organism input or persisted artifact is incomplete or unsafe."""


class EpisodeStatus(str, Enum):
    ISSUED = "ISSUED"
    SETTLED = "SETTLED"
    DISSOLVED = "DISSOLVED"


class DecisionKind(str, Enum):
    FORECAST_YES = "FORECAST_YES"
    FORECAST_NO = "FORECAST_NO"
    ABSTAIN = "ABSTAIN"


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EpisodeValidationError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return utc(value).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return utc(value)
    try:
        return utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError as exc:
        raise EpisodeValidationError("invalid ISO timestamp") from exc


def freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EpisodeValidationError("artifact floats must be finite")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise EpisodeValidationError("artifact mapping keys must be strings")
        return MappingProxyType(
            {key: freeze_json(value[key]) for key in sorted(value)}
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    raise EpisodeValidationError(
        f"artifact contains non-JSON type: {type(value).__name__}"
    )


def thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        thaw_json(freeze_json(value)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def probability(value: float, *, field_name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise EpisodeValidationError(f"{field_name} must be in [0, 1]")
    return parsed


@dataclass(frozen=True, slots=True)
class PointInTimeEvidence:
    """One raw or derived fact known no later than the decision clock."""

    evidence_id: str
    source_family: str
    observed_at: datetime
    received_at: datetime
    source_reference: str
    observed_at_verified: bool
    received_at_verified: bool
    payload: Mapping[str, Any]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "source_family", "source_reference"):
            if not getattr(self, field_name).strip():
                raise EpisodeValidationError(f"{field_name} must be non-empty")
        observed = utc(self.observed_at)
        received = utc(self.received_at)
        if observed > received:
            raise EpisodeValidationError("evidence observation occurs after receipt")
        if not self.observed_at_verified:
            raise EpisodeValidationError(
                "unverified provider timestamp cannot enter causal replay"
            )
        if not self.received_at_verified:
            raise EpisodeValidationError(
                "unverified receipt timestamp cannot enter causal replay"
            )
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "received_at", received)
        object.__setattr__(self, "payload", freeze_json(self.payload))
        limitations = tuple(sorted(item.strip() for item in self.limitations))
        if any(not item for item in limitations):
            raise EpisodeValidationError("evidence limitations contain an empty value")
        if len(set(limitations)) != len(limitations):
            raise EpisodeValidationError("evidence limitations contain duplicates")
        object.__setattr__(self, "limitations", limitations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_family": self.source_family,
            "observed_at": iso(self.observed_at),
            "received_at": iso(self.received_at),
            "source_reference": self.source_reference,
            "observed_at_verified": self.observed_at_verified,
            "received_at_verified": self.received_at_verified,
            "payload": thaw_json(self.payload),
            "limitations": list(self.limitations),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PointInTimeEvidence:
        return cls(
            evidence_id=str(data["evidence_id"]),
            source_family=str(data["source_family"]),
            observed_at=parse_iso(data["observed_at"]),
            received_at=parse_iso(data["received_at"]),
            source_reference=str(data["source_reference"]),
            observed_at_verified=data.get("observed_at_verified") is True,
            received_at_verified=data.get("received_at_verified") is True,
            payload=data.get("payload", {}),
            limitations=tuple(data.get("limitations", ())),
        )


@dataclass(frozen=True, slots=True)
class VerifiedSettlement:
    market_id: str
    event_cluster_id: str
    result_yes: bool
    market_closed_at: datetime
    settled_at: datetime
    received_at: datetime
    source: str
    source_reference: str
    verified: bool

    def __post_init__(self) -> None:
        for field_name in (
            "market_id",
            "event_cluster_id",
            "source",
            "source_reference",
        ):
            if not getattr(self, field_name).strip():
                raise EpisodeValidationError(f"{field_name} must be non-empty")
        if not isinstance(self.result_yes, bool):
            raise EpisodeValidationError("settlement result_yes must be boolean")
        closed = utc(self.market_closed_at)
        settled = utc(self.settled_at)
        received = utc(self.received_at)
        if not self.verified:
            raise EpisodeValidationError(
                "unverified settlement cannot complete a causal episode"
            )
        if not closed <= settled <= received:
            raise EpisodeValidationError("settlement clock violates causal order")
        object.__setattr__(self, "market_closed_at", closed)
        object.__setattr__(self, "settled_at", settled)
        object.__setattr__(self, "received_at", received)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_id": self.market_id,
            "event_cluster_id": self.event_cluster_id,
            "result_yes": self.result_yes,
            "market_closed_at": iso(self.market_closed_at),
            "settled_at": iso(self.settled_at),
            "received_at": iso(self.received_at),
            "source": self.source,
            "source_reference": self.source_reference,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VerifiedSettlement:
        return cls(
            market_id=str(data["market_id"]),
            event_cluster_id=str(data["event_cluster_id"]),
            result_yes=data["result_yes"],
            market_closed_at=parse_iso(data["market_closed_at"]),
            settled_at=parse_iso(data["settled_at"]),
            received_at=parse_iso(data["received_at"]),
            source=str(data["source"]),
            source_reference=str(data["source_reference"]),
            verified=data.get("verified") is True,
        )


@dataclass(frozen=True, slots=True)
class HeldOutCase:
    """A distinct, already-settled case used only for proposal replay."""

    case_id: str
    event_cluster_id: str
    market_prior_probability: float
    incumbent_probability: float
    result_yes: bool
    evidence_ids: tuple[str, ...]
    settlement_source_reference: str
    settlement_verified: bool

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.event_cluster_id.strip():
            raise EpisodeValidationError("held-out identifiers must be non-empty")
        if not isinstance(self.result_yes, bool):
            raise EpisodeValidationError("held-out result_yes must be boolean")
        if not self.settlement_source_reference.strip():
            raise EpisodeValidationError(
                "held-out settlement source reference must be non-empty"
            )
        if not self.settlement_verified:
            raise EpisodeValidationError(
                "unverified held-out settlement cannot enter replay"
            )
        object.__setattr__(
            self,
            "market_prior_probability",
            probability(
                self.market_prior_probability,
                field_name="market_prior_probability",
            ),
        )
        object.__setattr__(
            self,
            "incumbent_probability",
            probability(self.incumbent_probability, field_name="incumbent_probability"),
        )
        evidence = tuple(sorted(item.strip() for item in self.evidence_ids))
        if not evidence or any(not item for item in evidence):
            raise EpisodeValidationError("held-out case requires evidence_ids")
        if len(set(evidence)) != len(evidence):
            raise EpisodeValidationError("held-out evidence_ids contain duplicates")
        object.__setattr__(self, "evidence_ids", evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "event_cluster_id": self.event_cluster_id,
            "market_prior_probability": self.market_prior_probability,
            "incumbent_probability": self.incumbent_probability,
            "result_yes": self.result_yes,
            "evidence_ids": list(self.evidence_ids),
            "settlement_source_reference": self.settlement_source_reference,
            "settlement_verified": self.settlement_verified,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> HeldOutCase:
        return cls(
            case_id=str(data["case_id"]),
            event_cluster_id=str(data["event_cluster_id"]),
            market_prior_probability=float(data["market_prior_probability"]),
            incumbent_probability=float(data["incumbent_probability"]),
            result_yes=data["result_yes"],
            evidence_ids=tuple(data["evidence_ids"]),
            settlement_source_reference=str(data["settlement_source_reference"]),
            settlement_verified=data.get("settlement_verified") is True,
        )


@dataclass(frozen=True, slots=True)
class IssueRequest:
    market_id: str
    market_type: str
    vertical: AgentVertical
    clock_domain: ClockDomain
    objective: str
    policy_version: str
    decision_at: datetime
    market_close_at: datetime
    event_cluster_id: str
    evidence: tuple[PointInTimeEvidence, ...]
    max_shadow_contracts: int = 1

    def __post_init__(self) -> None:
        for field_name in (
            "market_id",
            "market_type",
            "objective",
            "policy_version",
            "event_cluster_id",
        ):
            if not getattr(self, field_name).strip():
                raise EpisodeValidationError(f"{field_name} must be non-empty")
        decision = utc(self.decision_at)
        close = utc(self.market_close_at)
        if decision > close:
            raise EpisodeValidationError("decision occurs after market close")
        if self.max_shadow_contracts <= 0:
            raise EpisodeValidationError("max_shadow_contracts must be positive")
        evidence = tuple(sorted(self.evidence, key=lambda item: item.evidence_id))
        if not evidence:
            raise EpisodeValidationError("episode requires point-in-time evidence")
        ids = tuple(item.evidence_id for item in evidence)
        if len(set(ids)) != len(ids):
            raise EpisodeValidationError("episode evidence_ids contain duplicates")
        if any(item.received_at > decision for item in evidence):
            raise EpisodeValidationError("future-received evidence cannot enter decision")
        object.__setattr__(self, "decision_at", decision)
        object.__setattr__(self, "market_close_at", close)
        object.__setattr__(self, "evidence", evidence)

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "market_id": self.market_id,
            "market_type": self.market_type,
            "vertical": self.vertical.value,
            "clock_domain": self.clock_domain.value,
            "objective": self.objective,
            "policy_version": self.policy_version,
            "decision_at": iso(self.decision_at),
            "market_close_at": iso(self.market_close_at),
            "event_cluster_id": self.event_cluster_id,
            "evidence": [item.to_dict() for item in self.evidence],
            "max_shadow_contracts": self.max_shadow_contracts,
        }

    def episode_id(self) -> str:
        return str(
            uuid.uuid5(
                _EPISODE_NAMESPACE,
                canonical_json(self.semantic_dict()),
            )
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IssueRequest:
        return cls(
            market_id=str(data["market_id"]),
            market_type=str(data["market_type"]),
            vertical=AgentVertical(str(data["vertical"])),
            clock_domain=ClockDomain(str(data["clock_domain"])),
            objective=str(data["objective"]),
            policy_version=str(data["policy_version"]),
            decision_at=parse_iso(data["decision_at"]),
            market_close_at=parse_iso(data["market_close_at"]),
            event_cluster_id=str(data["event_cluster_id"]),
            evidence=tuple(
                PointInTimeEvidence.from_dict(item) for item in data["evidence"]
            ),
            max_shadow_contracts=int(data.get("max_shadow_contracts", 1)),
        )


@dataclass(frozen=True, slots=True)
class EpisodeRequest:
    issue: IssueRequest
    settlement: VerifiedSettlement
    held_out_cases: tuple[HeldOutCase, ...]

    def __post_init__(self) -> None:
        if self.settlement.market_id != self.issue.market_id:
            raise EpisodeValidationError("settlement market differs from request")
        if self.settlement.event_cluster_id != self.issue.event_cluster_id:
            raise EpisodeValidationError("settlement cluster differs from request")
        if self.settlement.market_closed_at != self.issue.market_close_at:
            raise EpisodeValidationError("settlement close clock differs from request")
        held_out = tuple(sorted(self.held_out_cases, key=lambda item: item.case_id))
        held_ids = tuple(item.case_id for item in held_out)
        if len(set(held_ids)) != len(held_ids):
            raise EpisodeValidationError("held-out case_ids contain duplicates")
        if any(
            item.event_cluster_id == self.issue.event_cluster_id
            for item in held_out
        ):
            raise EpisodeValidationError(
                "held-out replay cannot reuse the decision event cluster"
            )
        held_clusters = tuple(item.event_cluster_id for item in held_out)
        if not held_out:
            raise EpisodeValidationError(
                "complete episode requires verified held-out replay evidence"
            )
        if len(set(held_clusters)) != len(held_clusters):
            raise EpisodeValidationError(
                "held-out replay cases must use unique event clusters"
            )
        object.__setattr__(self, "held_out_cases", held_out)

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "issue": self.issue.semantic_dict(),
            "settlement": self.settlement.to_dict(),
            "held_out_cases": [item.to_dict() for item in self.held_out_cases],
        }

    def episode_id(self) -> str:
        return self.issue.episode_id()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpisodeRequest:
        issue_data = data.get("issue")
        if issue_data is None:
            issue_keys = {
                "market_id",
                "market_type",
                "vertical",
                "clock_domain",
                "objective",
                "policy_version",
                "decision_at",
                "market_close_at",
                "event_cluster_id",
                "evidence",
                "max_shadow_contracts",
            }
            issue_data = {key: data[key] for key in issue_keys if key in data}
        return cls(
            issue=IssueRequest.from_dict(issue_data),
            settlement=VerifiedSettlement.from_dict(data["settlement"]),
            held_out_cases=tuple(
                HeldOutCase.from_dict(item) for item in data["held_out_cases"]
            ),
        )


@dataclass(frozen=True, slots=True)
class CompetingFuture:
    future_id: str
    agent_id: str
    label: str
    probability_yes: float
    source_family: str
    assumptions: tuple[str, ...]
    failure_conditions: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("future_id", "agent_id", "label", "source_family"):
            if not getattr(self, field_name).strip():
                raise EpisodeValidationError(f"{field_name} must be non-empty")
        object.__setattr__(
            self,
            "probability_yes",
            probability(self.probability_yes, field_name="probability_yes"),
        )
        for field_name in ("assumptions", "failure_conditions", "evidence_ids"):
            values = tuple(sorted(item.strip() for item in getattr(self, field_name)))
            if not values or any(not item for item in values):
                raise EpisodeValidationError(f"{field_name} must be non-empty")
            if len(set(values)) != len(values):
                raise EpisodeValidationError(f"{field_name} contains duplicates")
            object.__setattr__(self, field_name, values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "future_id": self.future_id,
            "agent_id": self.agent_id,
            "label": self.label,
            "probability_yes": self.probability_yes,
            "source_family": self.source_family,
            "assumptions": list(self.assumptions),
            "failure_conditions": list(self.failure_conditions),
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class EpisodeStep:
    number: int
    name: str
    status: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 1 <= self.number <= 20:
            raise EpisodeValidationError("episode step number must be in [1, 20]")
        if not self.name.strip() or not self.status.strip():
            raise EpisodeValidationError("episode step name and status are required")
        evidence = tuple(sorted(item.strip() for item in self.evidence_ids))
        if not evidence or any(not item for item in evidence):
            raise EpisodeValidationError("episode step requires evidence_ids")
        object.__setattr__(self, "evidence_ids", evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "name": self.name,
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class IssuedEpisodeArtifact:
    """Decision-time artifact that cannot contain settlement or replay truth."""

    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        frozen = freeze_json(self.payload)
        steps = frozen.get("capability_steps", ())
        numbers = tuple(step.get("number") for step in steps)
        if numbers != tuple(range(1, 14)):
            raise EpisodeValidationError("issued episode must record steps 1 through 13")
        names = tuple(step.get("name") for step in steps)
        if names != CAPABILITY_STEP_NAMES[:13]:
            raise EpisodeValidationError("issued episode capability names are invalid")
        if any(step.get("status") != "COMPLETE" for step in steps):
            raise EpisodeValidationError("issued episode contains an incomplete step")
        if any(not step.get("evidence_ids") for step in steps):
            raise EpisodeValidationError("issued episode step lacks evidence")
        if frozen.get("status") != EpisodeStatus.ISSUED.value:
            raise EpisodeValidationError("decision-time episode must be ISSUED")
        if frozen.get("maturity") != VNEXT_MATURITY:
            raise EpisodeValidationError("issued episode maturity label is missing")
        future_fields = {
            "settlement",
            "agent_grades",
            "calibration_and_trust_proposals",
            "bounded_improvement_proposal",
            "held_out_replay",
            "promotion_candidate",
        }
        if future_fields.intersection(frozen):
            raise EpisodeValidationError("issued episode contains future truth")
        try:
            issue_request = IssueRequest.from_dict(frozen.get("issue_request", {}))
        except (KeyError, TypeError, ValueError) as exc:
            raise EpisodeValidationError("issued episode input is invalid") from exc
        if frozen.get("episode_id") != issue_request.episode_id():
            raise EpisodeValidationError("issued episode ID differs from frozen input")
        governance = frozen.get("governance", {})
        if (
            governance.get("execution_authority") is not False
            or governance.get("promotion_authority") != "HUMAN_ONLY"
            or governance.get("incumbent_substitution_allowed") is not False
        ):
            raise EpisodeValidationError("issued episode governance boundary is unsafe")
        morphology = frozen.get("morphology", {})
        if morphology.get("dissolved_after_issuance") is not True:
            raise EpisodeValidationError("temporary organism was not dissolved")
        for history in morphology.get("lifecycle", {}).values():
            if not history or history[-1].get("current") != "RETIRED":
                raise EpisodeValidationError("participating agent was not retired")
        execution = frozen.get("shadow_execution", {})
        if (
            execution.get("lane") != "shadow"
            or execution.get("realized") is not False
            or execution.get("broker_contacted") is not False
            or execution.get("order_submitted") is not False
        ):
            raise EpisodeValidationError("issued shadow execution truth is unsafe")
        decision = frozen.get("decision", {})
        if decision.get("incumbent_substituted") is not False:
            raise EpisodeValidationError("issued episode substituted for incumbent")
        if decision.get("frozen") is not True:
            raise EpisodeValidationError("issued decision is not frozen")
        if frozen.get("decision_digest") != digest_json(decision):
            raise EpisodeValidationError("issued decision digest is invalid")
        object.__setattr__(self, "payload", frozen)

    @property
    def episode_id(self) -> str:
        return str(self.payload["episode_id"])

    def to_dict(self) -> dict[str, Any]:
        return thaw_json(self.payload)

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EpisodeArtifact:
    """A complete, immutable Phase 3 episode retained after dissolution."""

    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        frozen = freeze_json(self.payload)
        steps = frozen.get("capability_steps", ())
        numbers = tuple(step.get("number") for step in steps)
        if numbers != tuple(range(1, 21)):
            raise EpisodeValidationError("complete episode must record steps 1 through 20")
        names = tuple(step.get("name") for step in steps)
        if names != CAPABILITY_STEP_NAMES:
            raise EpisodeValidationError("complete episode capability names are invalid")
        if any(step.get("status") != "COMPLETE" for step in steps):
            raise EpisodeValidationError("complete episode contains an incomplete step")
        if any(not step.get("evidence_ids") for step in steps):
            raise EpisodeValidationError("complete episode step lacks evidence")
        if frozen.get("status") != EpisodeStatus.DISSOLVED.value:
            raise EpisodeValidationError("complete episode must be dissolved")
        if frozen.get("maturity") != VNEXT_MATURITY:
            raise EpisodeValidationError("episode maturity label is missing")
        governance = frozen.get("governance", {})
        if (
            governance.get("execution_authority") is not False
            or governance.get("promotion_authority") != "HUMAN_ONLY"
            or governance.get("incumbent_substitution_allowed") is not False
        ):
            raise EpisodeValidationError("episode governance boundary is unsafe")
        morphology = frozen.get("morphology", {})
        if morphology.get("dissolved_after_issuance") is not True:
            raise EpisodeValidationError("temporary organism was not dissolved")
        for history in morphology.get("lifecycle", {}).values():
            if not history or history[-1].get("current") != "RETIRED":
                raise EpisodeValidationError("participating agent was not retired")
        execution = frozen.get("shadow_execution", {})
        if (
            execution.get("lane") != "shadow"
            or execution.get("realized") is not False
            or execution.get("broker_contacted") is not False
            or execution.get("order_submitted") is not False
        ):
            raise EpisodeValidationError("shadow execution truth is unsafe")
        settlement = frozen.get("settlement", {})
        if (
            settlement.get("verified") is not True
            or settlement.get("lane") != "shadow"
            or settlement.get("realized_capital_pnl") is not False
        ):
            raise EpisodeValidationError("settlement truth is unsafe")
        decision = frozen.get("decision", {})
        if decision.get("incumbent_substituted") is not False:
            raise EpisodeValidationError("episode substituted for the incumbent")
        promotion = frozen.get("promotion_candidate", {})
        if (
            promotion.get("automatic_promotion") is not False
            or promotion.get("eligible_for_promotion") is not False
            or promotion.get("applied") is not False
        ):
            raise EpisodeValidationError("episode promotion boundary is unsafe")
        issued_payload = thaw_json(frozen)
        for field_name in (
            "issuance_digest",
            "settlement",
            "agent_grades",
            "calibration_and_trust_proposals",
            "bounded_improvement_proposal",
            "held_out_replay",
            "promotion_candidate",
            "ledger_record_id",
        ):
            issued_payload.pop(field_name, None)
        issued_payload["status"] = EpisodeStatus.ISSUED.value
        issued_payload["capability_steps"] = issued_payload["capability_steps"][:13]
        try:
            issued = IssuedEpisodeArtifact(issued_payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise EpisodeValidationError(
                "completed episode contains an invalid issuance"
            ) from exc
        if frozen.get("issuance_digest") != issued.digest():
            raise EpisodeValidationError("completed episode issuance digest is invalid")
        object.__setattr__(self, "payload", frozen)

    @property
    def episode_id(self) -> str:
        return str(self.payload["episode_id"])

    def to_dict(self) -> dict[str, Any]:
        return thaw_json(self.payload)

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
