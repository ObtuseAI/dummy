"""Typed, content-addressed contracts for nested forecast autoresearch."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from dummy.constitution import Authority, assert_authority_at_most
from dummy.world_model.models import digest_json


class AutoresearchValidationError(ValueError):
    """An autoresearch artifact violates a causal or governance boundary."""


class EvaluationPartition(str, Enum):
    VISIBLE_DEVELOPMENT = "VISIBLE_DEVELOPMENT"
    PRIVATE_SELECTION = "PRIVATE_SELECTION"
    EXTERNAL_GENERALIZATION = "EXTERNAL_GENERALIZATION"


class ResearchRole(str, Enum):
    FORECASTER = "FORECASTER"
    ADVERSARY = "ADVERSARY"
    CALIBRATOR = "CALIBRATOR"
    EVOLUTION_DEBUGGER = "EVOLUTION_DEBUGGER"


def utc(value: datetime | str) -> datetime:
    try:
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
    except ValueError as exc:
        raise AutoresearchValidationError("invalid autoresearch timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AutoresearchValidationError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return utc(value).isoformat().replace("+00:00", "Z")


def probability(value: float, *, field: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise AutoresearchValidationError(f"{field} must be in [0, 1]")
    return parsed


def finite(value: float, *, field: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise AutoresearchValidationError(f"{field} must be finite")
    return parsed


def nonempty(values: tuple[str, ...], *, field: str) -> tuple[str, ...]:
    normalized = tuple(str(item).strip() for item in values)
    if not normalized or any(not item for item in normalized):
        raise AutoresearchValidationError(f"{field} must be non-empty")
    return normalized


@dataclass(frozen=True, slots=True)
class ResearchTask:
    """One immutable, point-in-time forecast comparison.

    Private tasks may enter only the protected evaluator.  The outer researcher
    receives a :class:`PrivateEvaluationReceipt`, never these records.
    """

    case_id: str
    partition: EvaluationPartition
    event_cluster_id: str
    selection_keys: tuple[str, ...]
    decision_at: datetime
    market_close_at: datetime
    settlement_received_at: datetime
    candidate_probability: float | None
    incumbent_probability: float
    market_prior_probability: float
    result_yes: bool
    transfer_group: str
    regime: str
    evidence_ids: tuple[str, ...]
    candidate_abstained: bool = False
    abstention_was_correct: bool = False
    forced_coverage: bool = False
    point_in_time_verified: bool = True
    settlement_verified: bool = True
    evidence_reality: str = "VERIFIED_SETTLEMENT"
    source_family_ids: tuple[str, ...] = ("independent-source",)
    candidate_compute_units: float = 1.0
    incumbent_compute_units: float = 1.0
    candidate_cost_microunits: float = 1.0
    incumbent_cost_microunits: float = 1.0
    candidate_fill_verified: bool = False
    incumbent_fill_verified: bool = False
    candidate_claimed_fill_performance: bool = False
    candidate_pnl_cents: int = 0
    incumbent_pnl_cents: int = 0
    candidate_counterfactual_pnl_cents: int = 0
    replay_digest: str = "replay"
    repeated_replay_digest: str = "replay"
    candidate_used_future_evidence: bool = False
    candidate_marked_promotion_eligible: bool = False
    candidate_claimed_contested: bool = False
    claimed_independent_units: int = 1
    book_valid: bool = True
    candidate_used_book: bool = True
    lineup_received_at: datetime | None = None
    candidate_used_lineup: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "case_id",
            "event_cluster_id",
            "transfer_group",
            "regime",
            "evidence_reality",
            "replay_digest",
            "repeated_replay_digest",
        ):
            if not str(getattr(self, field_name)).strip():
                raise AutoresearchValidationError(f"{field_name} is required")
        decision = utc(self.decision_at)
        close = utc(self.market_close_at)
        settlement = utc(self.settlement_received_at)
        if not decision <= close <= settlement:
            raise AutoresearchValidationError("task violates causal time ordering")
        if type(self.result_yes) is not bool:
            raise AutoresearchValidationError("result_yes must be boolean")
        if self.candidate_abstained is (self.candidate_probability is not None):
            raise AutoresearchValidationError(
                "abstention requires no candidate probability; forecasts require one"
            )
        if self.candidate_probability is not None:
            object.__setattr__(
                self,
                "candidate_probability",
                probability(self.candidate_probability, field="candidate_probability"),
            )
        for field_name in ("incumbent_probability", "market_prior_probability"):
            object.__setattr__(
                self,
                field_name,
                probability(getattr(self, field_name), field=field_name),
            )
        for field_name in (
            "candidate_compute_units",
            "incumbent_compute_units",
            "candidate_cost_microunits",
            "incumbent_cost_microunits",
        ):
            value = finite(getattr(self, field_name), field=field_name)
            if value <= 0.0:
                raise AutoresearchValidationError(f"{field_name} must be positive")
            object.__setattr__(self, field_name, value)
        if self.claimed_independent_units < 1:
            raise AutoresearchValidationError(
                "claimed_independent_units must be positive"
            )
        raw_selection_keys = nonempty(self.selection_keys, field="selection_keys")
        raw_evidence_ids = nonempty(self.evidence_ids, field="evidence_ids")
        if len(set(raw_selection_keys)) != len(raw_selection_keys):
            raise AutoresearchValidationError("selection_keys contains duplicates")
        if len(set(raw_evidence_ids)) != len(raw_evidence_ids):
            raise AutoresearchValidationError("evidence_ids contains duplicates")
        selection_keys = tuple(sorted(raw_selection_keys))
        evidence_ids = tuple(sorted(raw_evidence_ids))
        source_families = nonempty(self.source_family_ids, field="source_family_ids")
        object.__setattr__(self, "decision_at", decision)
        object.__setattr__(self, "market_close_at", close)
        object.__setattr__(self, "settlement_received_at", settlement)
        object.__setattr__(self, "selection_keys", selection_keys)
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "source_family_ids", source_families)
        if self.lineup_received_at is not None:
            object.__setattr__(self, "lineup_received_at", utc(self.lineup_received_at))

    @property
    def replay_stable(self) -> bool:
        return self.replay_digest == self.repeated_replay_digest

    @property
    def outcome(self) -> float:
        return float(self.result_yes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "partition": self.partition.value,
            "event_cluster_id": self.event_cluster_id,
            "selection_keys": list(self.selection_keys),
            "decision_at": iso(self.decision_at),
            "market_close_at": iso(self.market_close_at),
            "settlement_received_at": iso(self.settlement_received_at),
            "candidate_probability": self.candidate_probability,
            "incumbent_probability": self.incumbent_probability,
            "market_prior_probability": self.market_prior_probability,
            "result_yes": self.result_yes,
            "transfer_group": self.transfer_group,
            "regime": self.regime,
            "evidence_ids": list(self.evidence_ids),
            "candidate_abstained": self.candidate_abstained,
            "abstention_was_correct": self.abstention_was_correct,
            "forced_coverage": self.forced_coverage,
            "point_in_time_verified": self.point_in_time_verified,
            "settlement_verified": self.settlement_verified,
            "evidence_reality": self.evidence_reality,
            "source_family_ids": list(self.source_family_ids),
            "candidate_compute_units": self.candidate_compute_units,
            "incumbent_compute_units": self.incumbent_compute_units,
            "candidate_cost_microunits": self.candidate_cost_microunits,
            "incumbent_cost_microunits": self.incumbent_cost_microunits,
            "candidate_fill_verified": self.candidate_fill_verified,
            "incumbent_fill_verified": self.incumbent_fill_verified,
            "candidate_claimed_fill_performance": self.candidate_claimed_fill_performance,
            "candidate_pnl_cents": self.candidate_pnl_cents,
            "incumbent_pnl_cents": self.incumbent_pnl_cents,
            "candidate_counterfactual_pnl_cents": self.candidate_counterfactual_pnl_cents,
            "replay_digest": self.replay_digest,
            "repeated_replay_digest": self.repeated_replay_digest,
            "candidate_used_future_evidence": self.candidate_used_future_evidence,
            "candidate_marked_promotion_eligible": self.candidate_marked_promotion_eligible,
            "candidate_claimed_contested": self.candidate_claimed_contested,
            "claimed_independent_units": self.claimed_independent_units,
            "book_valid": self.book_valid,
            "candidate_used_book": self.candidate_used_book,
            "lineup_received_at": (
                iso(self.lineup_received_at)
                if self.lineup_received_at is not None
                else None
            ),
            "candidate_used_lineup": self.candidate_used_lineup,
        }


@dataclass(frozen=True, slots=True)
class TaskSuite:
    suite_id: str
    tasks: tuple[ResearchTask, ...]
    sealed: bool = True

    def __post_init__(self) -> None:
        tasks = tuple(sorted(self.tasks, key=lambda item: item.case_id))
        if not tasks or len({item.case_id for item in tasks}) != len(tasks):
            raise AutoresearchValidationError("task suite IDs must be non-empty and unique")
        partitions = {item.partition for item in tasks}
        if partitions != set(EvaluationPartition):
            raise AutoresearchValidationError("all three evaluation partitions are required")
        for attribute in ("event_cluster_id",):
            seen: dict[str, EvaluationPartition] = {}
            for task in tasks:
                value = str(getattr(task, attribute))
                previous = seen.setdefault(value, task.partition)
                if previous is not task.partition:
                    raise AutoresearchValidationError(
                        f"{attribute} crosses evaluation partitions"
                    )
        seen_dates: dict[str, EvaluationPartition] = {}
        for task in tasks:
            value = task.decision_at.date().isoformat()
            previous = seen_dates.setdefault(value, task.partition)
            if previous is not task.partition:
                raise AutoresearchValidationError(
                    f"decision date crosses evaluation partitions: {value}"
                )
        for label, extractor in (
            ("selection key", lambda task: task.selection_keys),
            ("evidence ID", lambda task: task.evidence_ids),
        ):
            seen_values: dict[str, EvaluationPartition] = {}
            for task in tasks:
                for value in extractor(task):
                    previous = seen_values.setdefault(value, task.partition)
                    if previous is not task.partition:
                        raise AutoresearchValidationError(
                            f"{label} crosses evaluation partitions: {value}"
                        )
        if not self.sealed:
            raise AutoresearchValidationError("task suites must be sealed")
        object.__setattr__(self, "tasks", tasks)
        if self.suite_id != digest_json(self.semantic_dict()):
            raise AutoresearchValidationError("task suite ID does not match contents")

    @classmethod
    def create(cls, tasks: tuple[ResearchTask, ...]) -> TaskSuite:
        ordered = tuple(sorted(tasks, key=lambda item: item.case_id))
        semantic = {
            "schema_version": 1,
            "tasks": [item.to_dict() for item in ordered],
            "sealed": True,
            "selection_uses_external": False,
        }
        return cls(suite_id=digest_json(semantic), tasks=ordered)

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "tasks": [item.to_dict() for item in self.tasks],
            "sealed": self.sealed,
            "selection_uses_external": False,
        }

    def partition(self, value: EvaluationPartition) -> tuple[ResearchTask, ...]:
        return tuple(item for item in self.tasks if item.partition is value)

    def partition_manifest(self) -> dict[str, Any]:
        return {
            partition.value: {
                "task_count": len(self.partition(partition)),
                "event_cluster_count": len(
                    {item.event_cluster_id for item in self.partition(partition)}
                ),
                "item_details_exposed_to_outer_loop": (
                    partition is EvaluationPartition.VISIBLE_DEVELOPMENT
                ),
                "selection_eligible": partition is EvaluationPartition.PRIVATE_SELECTION,
            }
            for partition in EvaluationPartition
        }


@dataclass(frozen=True, slots=True)
class ComplexityProfile:
    changed_modules: int = 0
    cyclomatic_delta: int = 0
    new_branches: int = 0
    new_configuration_values: int = 0
    state_space_growth: int = 0
    added_dependencies: int = 0
    new_artifact_schemas: int = 0
    replay_cost_delta: float = 0.0
    explanation_complexity: int = 0
    dead_code_items: int = 0
    test_surface_expansion: int = 0

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = finite(getattr(self, field_name), field=field_name)
            if value < 0:
                raise AutoresearchValidationError(
                    f"complexity field cannot be negative: {field_name}"
                )

    def to_dict(self) -> dict[str, float | int]:
        return {
            field_name: getattr(self, field_name)
            for field_name in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class MetricVector:
    contested_brier_improvement: float
    log_loss_improvement: float
    calibration_improvement: float
    useful_sharpness: float
    fill_conditioned_improvement: float
    cross_regime_transfer: float
    abstention_quality: float
    information_per_cost: float
    drawdown_penalty: float
    complexity_penalty: float
    source_correlation_penalty: float
    reward_hacking_penalty: float
    replay_instability: float

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            finite(getattr(self, field_name), field=field_name)

    def to_dict(self) -> dict[str, float]:
        return {
            field_name: round(float(getattr(self, field_name)), 12)
            for field_name in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    evaluation_id: str
    candidate_id: str
    partition: EvaluationPartition
    metrics: MetricVector
    fitness: float
    hard_gates: tuple[tuple[str, bool], ...]
    accepted: bool
    task_count: int
    event_cluster_count: int
    confidence_interval: tuple[float, float] | None
    item_feedback: tuple[Mapping[str, Any], ...] = ()
    selection_eligible: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or self.task_count < 0:
            raise AutoresearchValidationError("evaluation identity is invalid")
        if self.event_cluster_count < 0 or self.event_cluster_count > self.task_count:
            raise AutoresearchValidationError("evaluation cluster count is invalid")
        if self.partition is EvaluationPartition.PRIVATE_SELECTION and self.item_feedback:
            raise AutoresearchValidationError("private evaluation cannot expose item feedback")
        expected_selection = self.partition is EvaluationPartition.PRIVATE_SELECTION
        if self.selection_eligible is not expected_selection:
            raise AutoresearchValidationError("selection eligibility violates partition law")
        if self.accepted and not all(passed for _, passed in self.hard_gates):
            raise AutoresearchValidationError("accepted evaluation has a failed hard gate")
        if self.evaluation_id != digest_json(self.semantic_dict()):
            raise AutoresearchValidationError("evaluation ID does not match contents")

    @classmethod
    def create(cls, **kwargs: Any) -> EvaluationSummary:
        probe = cls._semantic_from(kwargs)
        return cls(evaluation_id=digest_json(probe), **kwargs)

    @staticmethod
    def _semantic_from(data: Mapping[str, Any]) -> dict[str, Any]:
        interval = data.get("confidence_interval")
        metrics = data["metrics"]
        return {
            "schema_version": 1,
            "candidate_id": data["candidate_id"],
            "partition": data["partition"].value,
            "metrics": metrics.to_dict(),
            "fitness": round(float(data["fitness"]), 12),
            "hard_gates": [list(item) for item in data["hard_gates"]],
            "accepted": data["accepted"],
            "task_count": data["task_count"],
            "event_cluster_count": data["event_cluster_count"],
            "confidence_interval": list(interval) if interval else None,
            "item_feedback": [dict(item) for item in data.get("item_feedback", ())],
            "selection_eligible": data["selection_eligible"],
            "automatic_promotion": False,
            "execution_authority": False,
        }

    def semantic_dict(self) -> dict[str, Any]:
        return self._semantic_from(
            {
                "candidate_id": self.candidate_id,
                "partition": self.partition,
                "metrics": self.metrics,
                "fitness": self.fitness,
                "hard_gates": self.hard_gates,
                "accepted": self.accepted,
                "task_count": self.task_count,
                "event_cluster_count": self.event_cluster_count,
                "confidence_interval": self.confidence_interval,
                "item_feedback": self.item_feedback,
                "selection_eligible": self.selection_eligible,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {"evaluation_id": self.evaluation_id, **self.semantic_dict()}


@dataclass(frozen=True, slots=True)
class PrivateEvaluationReceipt:
    """The only private-evaluator information available to the outer loop."""

    evaluation_id: str
    candidate_id: str
    fitness: float
    accepted: bool
    gate_ids: tuple[str, ...]
    metric_digest: str
    task_count_bucket: str
    event_cluster_count_bucket: str

    @classmethod
    def from_summary(cls, summary: EvaluationSummary) -> PrivateEvaluationReceipt:
        if summary.partition is not EvaluationPartition.PRIVATE_SELECTION:
            raise AutoresearchValidationError("receipt requires private evaluation")

        def bucket(count: int) -> str:
            if count < 10:
                return "LT_10"
            if count < 50:
                return "10_49"
            if count < 200:
                return "50_199"
            return "GE_200"

        return cls(
            evaluation_id=summary.evaluation_id,
            candidate_id=summary.candidate_id,
            fitness=summary.fitness,
            accepted=summary.accepted,
            gate_ids=tuple(name for name, passed in summary.hard_gates if not passed),
            metric_digest=digest_json(summary.metrics.to_dict()),
            task_count_bucket=bucket(summary.task_count),
            event_cluster_count_bucket=bucket(summary.event_cluster_count),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "candidate_id": self.candidate_id,
            "fitness": round(self.fitness, 12),
            "accepted": self.accepted,
            "failed_gate_ids": list(self.gate_ids),
            "metric_digest": self.metric_digest,
            "task_count_bucket": self.task_count_bucket,
            "event_cluster_count_bucket": self.event_cluster_count_bucket,
            "item_details": None,
        }


@dataclass(frozen=True, slots=True)
class ResearchPolicy:
    policy_id: str
    label: str
    strategy: str
    lineage_ids: tuple[str, ...]
    authority: Authority = Authority.RECOMMEND
    evolved: bool = False

    def __post_init__(self) -> None:
        if not self.label.strip() or not self.strategy.strip():
            raise AutoresearchValidationError("research policy identity is required")
        lineages = tuple(sorted(set(nonempty(self.lineage_ids, field="lineage_ids"))))
        object.__setattr__(self, "lineage_ids", lineages)
        assert_authority_at_most(
            self.authority,
            Authority.RECOMMEND,
            component="outer evolution researcher",
        )
        if self.policy_id != digest_json(self.semantic_dict()):
            raise AutoresearchValidationError("research policy ID mismatch")

    @classmethod
    def create(
        cls,
        *,
        label: str,
        strategy: str,
        lineage_ids: tuple[str, ...],
        authority: Authority = Authority.RECOMMEND,
        evolved: bool = False,
    ) -> ResearchPolicy:
        semantic = {
            "schema_version": 1,
            "label": label,
            "strategy": strategy,
            "lineage_ids": sorted(set(lineage_ids)),
            "authority": authority.name,
            "evolved": evolved,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }
        return cls(policy_id=digest_json(semantic), label=label, strategy=strategy, lineage_ids=lineage_ids, authority=authority, evolved=evolved)

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "label": self.label,
            "strategy": self.strategy,
            "lineage_ids": list(self.lineage_ids),
            "authority": self.authority.name,
            "evolved": self.evolved,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }


__all__ = [
    "AutoresearchValidationError",
    "ComplexityProfile",
    "EvaluationPartition",
    "EvaluationSummary",
    "MetricVector",
    "PrivateEvaluationReceipt",
    "ResearchPolicy",
    "ResearchRole",
    "ResearchTask",
    "TaskSuite",
]
