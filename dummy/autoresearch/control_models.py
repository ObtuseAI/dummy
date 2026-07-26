"""Canonical, authority-free contracts for Dummy's research control plane.

These records wrap the older forecast, intelligence, and evolution contracts
without coercing their domain-specific genomes into one type.  All identifiers
are content addressed and all lifecycle changes are immutable events.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from dummy.world_model.models import digest_json, freeze_json, thaw_json

from .models import AutoresearchValidationError, iso, utc


class ResearchKind(str, Enum):
    INTELLIGENCE_PROTOCOL = "INTELLIGENCE_PROTOCOL"
    EVOLUTION_GENERATION = "EVOLUTION_GENERATION"
    NEGATIVE_CONTROL_AUDIT = "NEGATIVE_CONTROL_AUDIT"


class RunStatus(str, Enum):
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class EvaluationVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"


class CandidateStage(str, Enum):
    PROPOSED = "PROPOSED"
    PREREGISTERED = "PREREGISTERED"
    DEV_EVALUATED = "DEV_EVALUATED"
    PRIVATE_PASSED = "PRIVATE_PASSED"
    SEALED_REJECTED = "SEALED_REJECTED"
    FORWARD_PAPER = "FORWARD_PAPER"
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


_TRANSITIONS: dict[CandidateStage | None, frozenset[CandidateStage]] = {
    None: frozenset({CandidateStage.PROPOSED}),
    CandidateStage.PROPOSED: frozenset(
        {
            CandidateStage.PREREGISTERED,
            CandidateStage.REJECTED,
            CandidateStage.RETIRED,
        }
    ),
    CandidateStage.PREREGISTERED: frozenset(
        {
            CandidateStage.DEV_EVALUATED,
            CandidateStage.REJECTED,
            CandidateStage.RETIRED,
        }
    ),
    CandidateStage.DEV_EVALUATED: frozenset(
        {
            CandidateStage.PRIVATE_PASSED,
            CandidateStage.REJECTED,
            CandidateStage.RETIRED,
        }
    ),
    CandidateStage.PRIVATE_PASSED: frozenset(
        {
            CandidateStage.SEALED_REJECTED,
            CandidateStage.FORWARD_PAPER,
            CandidateStage.REJECTED,
            CandidateStage.RETIRED,
        }
    ),
    CandidateStage.FORWARD_PAPER: frozenset(
        {
            CandidateStage.READY_FOR_HUMAN_REVIEW,
            CandidateStage.REJECTED,
            CandidateStage.RETIRED,
        }
    ),
    CandidateStage.READY_FOR_HUMAN_REVIEW: frozenset(
        {CandidateStage.REJECTED, CandidateStage.RETIRED}
    ),
    CandidateStage.SEALED_REJECTED: frozenset({CandidateStage.RETIRED}),
    CandidateStage.REJECTED: frozenset({CandidateStage.RETIRED}),
    CandidateStage.RETIRED: frozenset(),
}


def _text(value: object, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise AutoresearchValidationError(f"{field} is required")
    return normalized


def _content_id(semantic: Mapping[str, Any]) -> str:
    return digest_json(dict(semantic))


def _frozen_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return freeze_json(dict(value))


@dataclass(frozen=True, slots=True)
class ResearchBudgetPolicy:
    """Hard defaults for one isolated research subprocess."""

    maximum_wall_seconds: int = 30
    maximum_cpu_seconds: int = 30
    maximum_memory_mb: int = 512
    maximum_input_bytes: int = 4_000_000
    maximum_output_bytes: int = 1_000_000
    maximum_disk_bytes: int = 8_000_000
    maximum_candidates: int = 96
    maximum_concurrency: int = 1
    maximum_cost_microunits: int = 0
    maximum_network_requests: int = 0
    maximum_credentials: int = 0
    network_access: bool = False
    credential_access: bool = False
    filesystem_write_scope: str = "EPHEMERAL_SANDBOX_ONLY"

    def __post_init__(self) -> None:
        for field in (
            "maximum_wall_seconds",
            "maximum_cpu_seconds",
            "maximum_memory_mb",
            "maximum_input_bytes",
            "maximum_output_bytes",
            "maximum_disk_bytes",
            "maximum_candidates",
            "maximum_concurrency",
        ):
            if int(getattr(self, field)) < 1:
                raise AutoresearchValidationError(f"{field} must be positive")
        if self.network_access or self.credential_access:
            raise AutoresearchValidationError(
                "research workers cannot receive network or credential access"
            )
        if self.maximum_concurrency != 1:
            raise AutoresearchValidationError(
                "the protected executor currently permits one child at a time"
            )
        if (
            self.maximum_cost_microunits != 0
            or self.maximum_network_requests != 0
            or self.maximum_credentials != 0
        ):
            raise AutoresearchValidationError(
                "research workers have zero spend, network, and credential budgets"
            )
        if self.filesystem_write_scope != "EPHEMERAL_SANDBOX_ONLY":
            raise AutoresearchValidationError(
                "research writes must remain inside the ephemeral sandbox"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ResearchBudgetPolicy:
        return cls(**{field: value[field] for field in cls.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class ResearchDefinition:
    definition_id: str
    plugin_id: str
    plugin_version: str
    kind: ResearchKind
    hypothesis_id: str
    candidate_id: str
    evaluator_id: str
    parameters: Mapping[str, Any]
    required_control_ids: tuple[str, ...]
    seed: int
    budget: ResearchBudgetPolicy

    def __post_init__(self) -> None:
        for field in (
            "plugin_id",
            "plugin_version",
            "hypothesis_id",
            "candidate_id",
            "evaluator_id",
        ):
            _text(getattr(self, field), field)
        controls = tuple(sorted({_text(item, "required_control_ids") for item in self.required_control_ids}))
        if not controls:
            raise AutoresearchValidationError("at least one negative control is required")
        if self.seed < 0:
            raise AutoresearchValidationError("seed cannot be negative")
        object.__setattr__(self, "required_control_ids", controls)
        object.__setattr__(self, "parameters", _frozen_mapping(self.parameters))
        if self.definition_id != _content_id(self.semantic_dict()):
            raise AutoresearchValidationError("research definition ID mismatch")

    @classmethod
    def create(cls, **kwargs: Any) -> ResearchDefinition:
        semantic = cls._semantic_from(kwargs)
        return cls(definition_id=_content_id(semantic), **kwargs)

    @staticmethod
    def _semantic_from(value: Mapping[str, Any]) -> dict[str, Any]:
        kind = value["kind"]
        budget = value["budget"]
        return {
            "schema_version": 1,
            "plugin_id": str(value["plugin_id"]).strip(),
            "plugin_version": str(value["plugin_version"]).strip(),
            "kind": kind.value if isinstance(kind, ResearchKind) else str(kind),
            "hypothesis_id": str(value["hypothesis_id"]).strip(),
            "candidate_id": str(value["candidate_id"]).strip(),
            "evaluator_id": str(value["evaluator_id"]).strip(),
            "parameters": thaw_json(freeze_json(value["parameters"])),
            "required_control_ids": sorted(set(value["required_control_ids"])),
            "seed": int(value["seed"]),
            "budget": (
                budget.to_dict()
                if isinstance(budget, ResearchBudgetPolicy)
                else dict(budget)
            ),
            "source_edit_applied": False,
            "runtime_application": False,
            "automatic_promotion": False,
            "execution_authority": False,
            "capital_authority": False,
        }

    def semantic_dict(self) -> dict[str, Any]:
        return self._semantic_from(
            {
                "plugin_id": self.plugin_id,
                "plugin_version": self.plugin_version,
                "kind": self.kind,
                "hypothesis_id": self.hypothesis_id,
                "candidate_id": self.candidate_id,
                "evaluator_id": self.evaluator_id,
                "parameters": self.parameters,
                "required_control_ids": self.required_control_ids,
                "seed": self.seed,
                "budget": self.budget,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {"definition_id": self.definition_id, **self.semantic_dict()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ResearchDefinition:
        return cls(
            definition_id=str(value["definition_id"]),
            plugin_id=str(value["plugin_id"]),
            plugin_version=str(value["plugin_version"]),
            kind=ResearchKind(str(value["kind"])),
            hypothesis_id=str(value["hypothesis_id"]),
            candidate_id=str(value["candidate_id"]),
            evaluator_id=str(value["evaluator_id"]),
            parameters=dict(value["parameters"]),
            required_control_ids=tuple(value["required_control_ids"]),
            seed=int(value["seed"]),
            budget=ResearchBudgetPolicy.from_dict(value["budget"]),
        )


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    snapshot_id: str
    domain_id: str
    captured_at: datetime
    source_ids: tuple[str, ...]
    source_family_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    point_in_time_verified: bool
    settlement_verified: bool

    def __post_init__(self) -> None:
        _text(self.domain_id, "domain_id")
        sources = tuple(sorted({_text(item, "source_ids") for item in self.source_ids}))
        families = tuple(
            sorted({_text(item, "source_family_ids") for item in self.source_family_ids})
        )
        if not sources or not families:
            raise AutoresearchValidationError(
                "evidence requires source and source-family identities"
            )
        object.__setattr__(self, "captured_at", utc(self.captured_at))
        object.__setattr__(self, "source_ids", sources)
        object.__setattr__(self, "source_family_ids", families)
        object.__setattr__(self, "payload", _frozen_mapping(self.payload))
        if self.snapshot_id != _content_id(self.semantic_dict()):
            raise AutoresearchValidationError("evidence snapshot ID mismatch")

    @classmethod
    def create(cls, **kwargs: Any) -> EvidenceSnapshot:
        semantic = cls._semantic_from(kwargs)
        return cls(snapshot_id=_content_id(semantic), **kwargs)

    @staticmethod
    def _semantic_from(value: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "domain_id": str(value["domain_id"]).strip(),
            "captured_at": iso(value["captured_at"]),
            "source_ids": sorted(set(value["source_ids"])),
            "source_family_ids": sorted(set(value["source_family_ids"])),
            "payload": thaw_json(freeze_json(value["payload"])),
            "point_in_time_verified": bool(value["point_in_time_verified"]),
            "settlement_verified": bool(value["settlement_verified"]),
            "execution_authority": False,
            "capital_authority": False,
        }

    def semantic_dict(self) -> dict[str, Any]:
        return self._semantic_from(
            {
                "domain_id": self.domain_id,
                "captured_at": self.captured_at,
                "source_ids": self.source_ids,
                "source_family_ids": self.source_family_ids,
                "payload": self.payload,
                "point_in_time_verified": self.point_in_time_verified,
                "settlement_verified": self.settlement_verified,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            **self.semantic_dict(),
        }

    @property
    def evidence_fingerprint(self) -> str:
        """Semantic evidence identity independent of scheduler observation time."""
        return digest_json(
            {
                "schema_version": 1,
                "domain_id": self.domain_id,
                "source_ids": list(self.source_ids),
                "source_family_ids": list(self.source_family_ids),
                "payload": thaw_json(self.payload),
                "point_in_time_verified": self.point_in_time_verified,
                "settlement_verified": self.settlement_verified,
            }
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EvidenceSnapshot:
        return cls(
            snapshot_id=str(value["snapshot_id"]),
            domain_id=str(value["domain_id"]),
            captured_at=utc(str(value["captured_at"])),
            source_ids=tuple(value["source_ids"]),
            source_family_ids=tuple(value["source_family_ids"]),
            payload=dict(value["payload"]),
            point_in_time_verified=bool(value["point_in_time_verified"]),
            settlement_verified=bool(value["settlement_verified"]),
        )


@dataclass(frozen=True, slots=True)
class ResearchRun:
    run_id: str
    run_key: str
    definition_id: str
    evidence_snapshot_id: str
    plugin_id: str
    evaluator_id: str
    started_at: datetime
    completed_at: datetime
    status: RunStatus
    result: Mapping[str, Any]
    wall_seconds: float
    subprocess_isolated: bool = True

    def __post_init__(self) -> None:
        for field in (
            "run_key",
            "definition_id",
            "evidence_snapshot_id",
            "plugin_id",
            "evaluator_id",
        ):
            _text(getattr(self, field), field)
        started = utc(self.started_at)
        completed = utc(self.completed_at)
        if completed < started:
            raise AutoresearchValidationError("research run completes before it starts")
        duration = float(self.wall_seconds)
        if not math.isfinite(duration) or duration < 0:
            raise AutoresearchValidationError("wall_seconds must be finite and nonnegative")
        if not self.subprocess_isolated:
            raise AutoresearchValidationError("research runs must be isolated")
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "completed_at", completed)
        object.__setattr__(self, "result", _frozen_mapping(self.result))
        if self.run_id != _content_id(self.semantic_dict()):
            raise AutoresearchValidationError("research run ID mismatch")

    @classmethod
    def create(cls, **kwargs: Any) -> ResearchRun:
        semantic = cls._semantic_from(kwargs)
        return cls(run_id=_content_id(semantic), **kwargs)

    @staticmethod
    def _semantic_from(value: Mapping[str, Any]) -> dict[str, Any]:
        status = value["status"]
        return {
            "schema_version": 1,
            "run_key": str(value["run_key"]),
            "definition_id": str(value["definition_id"]),
            "evidence_snapshot_id": str(value["evidence_snapshot_id"]),
            "plugin_id": str(value["plugin_id"]),
            "evaluator_id": str(value["evaluator_id"]),
            "started_at": iso(value["started_at"]),
            "completed_at": iso(value["completed_at"]),
            "status": status.value if isinstance(status, RunStatus) else str(status),
            "result": thaw_json(freeze_json(value["result"])),
            "wall_seconds": round(float(value["wall_seconds"]), 9),
            "subprocess_isolated": bool(value.get("subprocess_isolated", True)),
            "network_access": False,
            "credential_access": False,
            "source_edit_applied": False,
            "runtime_application": False,
            "automatic_promotion": False,
            "execution_authority": False,
            "capital_authority": False,
        }

    def semantic_dict(self) -> dict[str, Any]:
        return self._semantic_from(
            {
                "run_key": self.run_key,
                "definition_id": self.definition_id,
                "evidence_snapshot_id": self.evidence_snapshot_id,
                "plugin_id": self.plugin_id,
                "evaluator_id": self.evaluator_id,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "status": self.status,
                "result": self.result,
                "wall_seconds": self.wall_seconds,
                "subprocess_isolated": self.subprocess_isolated,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, **self.semantic_dict()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ResearchRun:
        return cls(
            run_id=str(value["run_id"]),
            run_key=str(value["run_key"]),
            definition_id=str(value["definition_id"]),
            evidence_snapshot_id=str(value["evidence_snapshot_id"]),
            plugin_id=str(value["plugin_id"]),
            evaluator_id=str(value["evaluator_id"]),
            started_at=utc(str(value["started_at"])),
            completed_at=utc(str(value["completed_at"])),
            status=RunStatus(str(value["status"])),
            result=dict(value["result"]),
            wall_seconds=float(value["wall_seconds"]),
            subprocess_isolated=bool(value["subprocess_isolated"]),
        )


@dataclass(frozen=True, slots=True)
class EvaluationReceipt:
    receipt_id: str
    run_id: str
    definition_id: str
    candidate_id: str
    evaluator_id: str
    evaluated_at: datetime
    verdict: EvaluationVerdict
    checks: tuple[tuple[str, bool], ...]
    metrics: Mapping[str, Any]
    negative_controls_passed: bool
    human_review_required: bool = True

    def __post_init__(self) -> None:
        for field in (
            "run_id",
            "definition_id",
            "candidate_id",
            "evaluator_id",
        ):
            _text(getattr(self, field), field)
        checks = tuple(sorted((_text(name, "check"), bool(passed)) for name, passed in self.checks))
        if len({name for name, _ in checks}) != len(checks):
            raise AutoresearchValidationError("evaluation checks contain duplicates")
        if self.verdict is EvaluationVerdict.PASS and (
            not self.negative_controls_passed
            or not checks
            or not all(passed for _, passed in checks)
        ):
            raise AutoresearchValidationError(
                "a passing receipt requires all negative and evaluator checks"
            )
        if not self.human_review_required:
            raise AutoresearchValidationError("positive promotion must require human review")
        object.__setattr__(self, "evaluated_at", utc(self.evaluated_at))
        object.__setattr__(self, "checks", checks)
        object.__setattr__(self, "metrics", _frozen_mapping(self.metrics))
        if self.receipt_id != _content_id(self.semantic_dict()):
            raise AutoresearchValidationError("evaluation receipt ID mismatch")

    @classmethod
    def create(cls, **kwargs: Any) -> EvaluationReceipt:
        semantic = cls._semantic_from(kwargs)
        return cls(receipt_id=_content_id(semantic), **kwargs)

    @staticmethod
    def _semantic_from(value: Mapping[str, Any]) -> dict[str, Any]:
        verdict = value["verdict"]
        return {
            "schema_version": 1,
            "run_id": str(value["run_id"]),
            "definition_id": str(value["definition_id"]),
            "candidate_id": str(value["candidate_id"]),
            "evaluator_id": str(value["evaluator_id"]),
            "evaluated_at": iso(value["evaluated_at"]),
            "verdict": verdict.value if isinstance(verdict, EvaluationVerdict) else str(verdict),
            "checks": [list(item) for item in sorted(value["checks"])],
            "metrics": thaw_json(freeze_json(value["metrics"])),
            "negative_controls_passed": bool(value["negative_controls_passed"]),
            "human_review_required": bool(value.get("human_review_required", True)),
            "private_item_details": None,
            "source_edit_applied": False,
            "runtime_application": False,
            "automatic_promotion": False,
            "execution_authority": False,
            "capital_authority": False,
        }

    def semantic_dict(self) -> dict[str, Any]:
        return self._semantic_from(
            {
                "run_id": self.run_id,
                "definition_id": self.definition_id,
                "candidate_id": self.candidate_id,
                "evaluator_id": self.evaluator_id,
                "evaluated_at": self.evaluated_at,
                "verdict": self.verdict,
                "checks": self.checks,
                "metrics": self.metrics,
                "negative_controls_passed": self.negative_controls_passed,
                "human_review_required": self.human_review_required,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.semantic_dict()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EvaluationReceipt:
        return cls(
            receipt_id=str(value["receipt_id"]),
            run_id=str(value["run_id"]),
            definition_id=str(value["definition_id"]),
            candidate_id=str(value["candidate_id"]),
            evaluator_id=str(value["evaluator_id"]),
            evaluated_at=utc(str(value["evaluated_at"])),
            verdict=EvaluationVerdict(str(value["verdict"])),
            checks=tuple((str(item[0]), bool(item[1])) for item in value["checks"]),
            metrics=dict(value["metrics"]),
            negative_controls_passed=bool(value["negative_controls_passed"]),
            human_review_required=bool(value["human_review_required"]),
        )


@dataclass(frozen=True, slots=True)
class CandidateStateEvent:
    event_id: str
    candidate_id: str
    previous_stage: CandidateStage | None
    stage: CandidateStage
    occurred_at: datetime
    reason: str
    receipt_ids: tuple[str, ...]
    human_authorized: bool = False

    def __post_init__(self) -> None:
        _text(self.candidate_id, "candidate_id")
        _text(self.reason, "reason")
        receipts = tuple(sorted({_text(item, "receipt_ids") for item in self.receipt_ids}))
        if self.stage not in _TRANSITIONS[self.previous_stage]:
            raise AutoresearchValidationError(
                f"invalid candidate transition: {self.previous_stage} -> {self.stage}"
            )
        if self.human_authorized:
            raise AutoresearchValidationError(
                "the research control plane does not perform human promotion"
            )
        object.__setattr__(self, "receipt_ids", receipts)
        object.__setattr__(self, "occurred_at", utc(self.occurred_at))
        if self.event_id != _content_id(self.semantic_dict()):
            raise AutoresearchValidationError("candidate state-event ID mismatch")

    @classmethod
    def create(cls, **kwargs: Any) -> CandidateStateEvent:
        semantic = cls._semantic_from(kwargs)
        return cls(event_id=_content_id(semantic), **kwargs)

    @staticmethod
    def _semantic_from(value: Mapping[str, Any]) -> dict[str, Any]:
        previous = value.get("previous_stage")
        stage = value["stage"]
        return {
            "schema_version": 1,
            "candidate_id": str(value["candidate_id"]),
            "previous_stage": (
                previous.value if isinstance(previous, CandidateStage) else previous
            ),
            "stage": stage.value if isinstance(stage, CandidateStage) else str(stage),
            "occurred_at": iso(value["occurred_at"]),
            "reason": str(value["reason"]).strip(),
            "receipt_ids": sorted(set(value["receipt_ids"])),
            "human_authorized": bool(value.get("human_authorized", False)),
            "production_integration": False,
            "automatic_promotion": False,
            "execution_authority": False,
            "capital_authority": False,
        }

    def semantic_dict(self) -> dict[str, Any]:
        return self._semantic_from(
            {
                "candidate_id": self.candidate_id,
                "previous_stage": self.previous_stage,
                "stage": self.stage,
                "occurred_at": self.occurred_at,
                "reason": self.reason,
                "receipt_ids": self.receipt_ids,
                "human_authorized": self.human_authorized,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, **self.semantic_dict()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> CandidateStateEvent:
        previous = value.get("previous_stage")
        return cls(
            event_id=str(value["event_id"]),
            candidate_id=str(value["candidate_id"]),
            previous_stage=CandidateStage(str(previous)) if previous else None,
            stage=CandidateStage(str(value["stage"])),
            occurred_at=utc(str(value["occurred_at"])),
            reason=str(value["reason"]),
            receipt_ids=tuple(value["receipt_ids"]),
            human_authorized=bool(value["human_authorized"]),
        )


def research_run_key(
    definition: ResearchDefinition,
    evidence: EvidenceSnapshot,
) -> str:
    return digest_json(
        {
            "schema_version": 1,
            "definition_id": definition.definition_id,
            "evidence_fingerprint": evidence.evidence_fingerprint,
            "plugin_id": definition.plugin_id,
            "plugin_version": definition.plugin_version,
            "evaluator_id": definition.evaluator_id,
        }
    )


__all__ = [
    "CandidateStage",
    "CandidateStateEvent",
    "EvaluationReceipt",
    "EvaluationVerdict",
    "EvidenceSnapshot",
    "ResearchBudgetPolicy",
    "ResearchDefinition",
    "ResearchKind",
    "ResearchRun",
    "RunStatus",
    "research_run_key",
]
