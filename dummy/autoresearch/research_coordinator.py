"""Single fail-closed coordinator for all Dummy research plugins."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from dummy.world_model.models import digest_json

from .control_models import (
    CandidateStage,
    CandidateStateEvent,
    EvaluationReceipt,
    EvaluationVerdict,
    EvidenceSnapshot,
    ResearchDefinition,
    ResearchRun,
    RunStatus,
    research_run_key,
)
from .isolated_executor import IsolatedResearchExecutor, WorkerExecution
from .models import AutoresearchValidationError, iso, utc
from .research_journal import ResearchJournal
from .research_plugins import intelligence_definition_from_protocol


@dataclass(frozen=True, slots=True)
class CoordinationResult:
    run: ResearchRun
    receipt: EvaluationReceipt
    state_events: tuple[CandidateStateEvent, ...]
    reused: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "run": self.run.to_dict(),
            "receipt": self.receipt.to_dict(),
            "state_events": [item.to_dict() for item in self.state_events],
            "reused": self.reused,
            "source_edit_applied": False,
            "runtime_application": False,
            "automatic_promotion": False,
            "execution_authority": False,
            "capital_authority": False,
        }


class ResearchCoordinator:
    def __init__(
        self,
        journal: ResearchJournal,
        *,
        executor: IsolatedResearchExecutor | None = None,
    ) -> None:
        self.journal = journal
        self.executor = executor or IsolatedResearchExecutor()

    def _append_state(
        self,
        *,
        candidate_id: str,
        previous_stage: CandidateStage | None,
        stage: CandidateStage,
        occurred_at: datetime,
        reason: str,
        receipt_ids: tuple[str, ...] = (),
    ) -> CandidateStateEvent:
        event = CandidateStateEvent.create(
            candidate_id=candidate_id,
            previous_stage=previous_stage,
            stage=stage,
            occurred_at=occurred_at,
            reason=reason,
            receipt_ids=receipt_ids,
        )
        self.journal.append_event(
            event_id=event.event_id,
            event_type="CANDIDATE_STATE",
            subject_id=candidate_id,
            semantic_key=event.event_id,
            occurred_at=occurred_at,
            payload=event.semantic_dict(),
        )
        return event

    def _latest_stage(self, candidate_id: str) -> CandidateStage | None:
        events = self.journal.candidate_events(candidate_id)
        if not events:
            return None
        parsed = [
            CandidateStateEvent.from_dict(
                {"event_id": item.event_id, **dict(item.payload)}
            )
            for item in events
        ]
        previous: CandidateStage | None = None
        for event in parsed:
            if event.previous_stage is not previous:
                raise AutoresearchValidationError(
                    "candidate lifecycle journal is discontinuous"
                )
            previous = event.stage
        return previous

    @staticmethod
    def _verdict(
        execution: WorkerExecution,
    ) -> tuple[EvaluationVerdict, tuple[tuple[str, bool], ...], bool]:
        result = execution.result
        controls = result.get("negative_controls") or {}
        raw_checks = controls.get("checks") or {}
        checks = {
            str(name): bool(passed)
            for name, passed in raw_checks.items()
        }
        authority_free = all(
            result.get(field) is False
            for field in (
                "source_edit_applied",
                "runtime_application",
                "automatic_promotion",
                "execution_authority",
                "capital_authority",
                "orders_placed",
            )
        )
        checks["worker_authority_free"] = authority_free
        controls_passed = bool(controls.get("passed")) and authority_free
        outcome = str(result.get("outcome") or "FAIL")
        if execution.status is RunStatus.BLOCKED or outcome == "BLOCKED":
            verdict = EvaluationVerdict.BLOCKED
        elif execution.status in {RunStatus.FAILED, RunStatus.TIMED_OUT}:
            verdict = EvaluationVerdict.FAIL
        elif outcome == "PASS" and controls_passed:
            verdict = EvaluationVerdict.PASS
        elif outcome == "INCONCLUSIVE" and controls_passed:
            verdict = EvaluationVerdict.INCONCLUSIVE
        else:
            verdict = EvaluationVerdict.FAIL
        return verdict, tuple(sorted(checks.items())), controls_passed

    def _existing(
        self,
        run_key: str,
    ) -> CoordinationResult | None:
        run_event = self.journal.find_event(
            event_type="RESEARCH_RUN",
            semantic_key=run_key,
        )
        if run_event is None:
            return None
        run = ResearchRun.from_dict(
            {"run_id": run_event.event_id, **dict(run_event.payload)}
        )
        receipt_event = self.journal.find_event(
            event_type="EVALUATION_RECEIPT",
            semantic_key=run.run_id,
        )
        if receipt_event is None:
            raise AutoresearchValidationError(
                "a completed research run is missing its evaluator receipt"
            )
        receipt = EvaluationReceipt.from_dict(
            {"receipt_id": receipt_event.event_id, **dict(receipt_event.payload)}
        )
        state_events = tuple(
            CandidateStateEvent.from_dict(
                {"event_id": item.event_id, **dict(item.payload)}
            )
            for item in self.journal.candidate_events(receipt.candidate_id)
            if receipt.receipt_id in tuple(item.payload.get("receipt_ids") or ())
        )
        return CoordinationResult(
            run=run,
            receipt=receipt,
            state_events=state_events,
            reused=True,
        )

    def run(
        self,
        definition: ResearchDefinition,
        evidence: EvidenceSnapshot,
        *,
        observed_at: datetime | None = None,
    ) -> CoordinationResult:
        now = utc(observed_at or datetime.now(timezone.utc))
        self.journal.store_definition(
            record_id=definition.definition_id,
            record_type="ResearchDefinition",
            semantic=definition.semantic_dict(),
            stored_at=now,
        )
        self.journal.store_definition(
            record_id=evidence.snapshot_id,
            record_type="EvidenceSnapshot",
            semantic=evidence.semantic_dict(),
            stored_at=now,
        )
        run_key = research_run_key(definition, evidence)
        existing = self._existing(run_key)
        if existing is not None:
            return existing

        state_events: list[CandidateStateEvent] = []
        stage = self._latest_stage(definition.candidate_id)
        if stage is None:
            proposed = self._append_state(
                candidate_id=definition.candidate_id,
                previous_stage=None,
                stage=CandidateStage.PROPOSED,
                occurred_at=now,
                reason="registered_plugin_proposal",
            )
            state_events.append(proposed)
            stage = CandidateStage.PROPOSED
        if stage is CandidateStage.PROPOSED:
            preregistered = self._append_state(
                candidate_id=definition.candidate_id,
                previous_stage=stage,
                stage=CandidateStage.PREREGISTERED,
                occurred_at=now,
                reason="immutable_definition_evidence_and_budget_registered",
            )
            state_events.append(preregistered)
            stage = CandidateStage.PREREGISTERED

        if stage in {
            CandidateStage.REJECTED,
            CandidateStage.RETIRED,
            CandidateStage.SEALED_REJECTED,
        }:
            execution = WorkerExecution(
                status=RunStatus.BLOCKED,
                started_at=now,
                completed_at=now,
                wall_seconds=0.0,
                result={
                    "worker_status": "BLOCKED",
                    "outcome": "BLOCKED",
                    "reason": f"CANDIDATE_{stage.value}",
                    "negative_controls": {"checks": {}, "passed": False},
                    "source_edit_applied": False,
                    "runtime_application": False,
                    "automatic_promotion": False,
                    "execution_authority": False,
                    "capital_authority": False,
                    "orders_placed": False,
                },
            )
        else:
            execution = self.executor.execute(definition, evidence)

        run = ResearchRun.create(
            run_key=run_key,
            definition_id=definition.definition_id,
            evidence_snapshot_id=evidence.snapshot_id,
            plugin_id=definition.plugin_id,
            evaluator_id=definition.evaluator_id,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            status=execution.status,
            result=execution.result,
            wall_seconds=execution.wall_seconds,
        )
        self.journal.append_event(
            event_id=run.run_id,
            event_type="RESEARCH_RUN",
            subject_id=definition.candidate_id,
            semantic_key=run.run_key,
            occurred_at=run.completed_at,
            payload=run.semantic_dict(),
        )
        verdict, checks, negative_controls_passed = self._verdict(execution)
        result = execution.result
        receipt = EvaluationReceipt.create(
            run_id=run.run_id,
            definition_id=definition.definition_id,
            candidate_id=definition.candidate_id,
            evaluator_id=definition.evaluator_id,
            evaluated_at=run.completed_at,
            verdict=verdict,
            checks=checks,
            metrics={
                "worker_status": result.get("worker_status"),
                "reason": result.get("reason"),
                "validated_effect": bool(result.get("validated_effect")),
                "worker_candidate_id": result.get("candidate_id"),
                "evolution_summary": result.get("evolution_summary"),
            },
            negative_controls_passed=negative_controls_passed,
        )
        self.journal.append_event(
            event_id=receipt.receipt_id,
            event_type="EVALUATION_RECEIPT",
            subject_id=definition.candidate_id,
            semantic_key=run.run_id,
            occurred_at=receipt.evaluated_at,
            payload=receipt.semantic_dict(),
        )

        stage = self._latest_stage(definition.candidate_id)
        if stage is CandidateStage.PREREGISTERED and verdict in {
            EvaluationVerdict.PASS,
            EvaluationVerdict.INCONCLUSIVE,
        }:
            evaluated = self._append_state(
                candidate_id=definition.candidate_id,
                previous_stage=stage,
                stage=CandidateStage.DEV_EVALUATED,
                occurred_at=run.completed_at,
                reason=(
                    "protected_development_evaluation_complete"
                    if verdict is EvaluationVerdict.PASS
                    else "development_evaluation_inconclusive"
                ),
                receipt_ids=(receipt.receipt_id,),
            )
            state_events.append(evaluated)
            stage = CandidateStage.DEV_EVALUATED
        elif stage is CandidateStage.PREREGISTERED and verdict is EvaluationVerdict.FAIL:
            rejected = self._append_state(
                candidate_id=definition.candidate_id,
                previous_stage=stage,
                stage=CandidateStage.REJECTED,
                occurred_at=run.completed_at,
                reason="protected_evaluator_or_negative_control_failure",
                receipt_ids=(receipt.receipt_id,),
            )
            state_events.append(rejected)
            stage = CandidateStage.REJECTED

        forward_failed = bool(
            ((result.get("evolution_summary") or {}).get("forward_failed"))
        )
        if (
            stage in {CandidateStage.DEV_EVALUATED, CandidateStage.REJECTED}
            and (
                forward_failed
                or (
                    verdict is EvaluationVerdict.FAIL
                    and not negative_controls_passed
                )
            )
        ):
            retired = self._append_state(
                candidate_id=definition.candidate_id,
                previous_stage=stage,
                stage=CandidateStage.RETIRED,
                occurred_at=run.completed_at,
                reason=(
                    "retired_failed_forward_epoch_after_diverse_evidence"
                    if forward_failed
                    else "retired_failed_adversarial_controls"
                ),
                receipt_ids=(receipt.receipt_id,),
            )
            state_events.append(retired)

        return CoordinationResult(
            run=run,
            receipt=receipt,
            state_events=tuple(state_events),
            reused=False,
        )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(
            dict(payload),
            handle,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        handle.write("\n")
    temporary.replace(path)


def consume_intelligence_queue(
    *,
    queue_path: Path,
    journal_path: Path,
    report_path: Path,
    evidence: EvidenceSnapshot,
    generated_at: datetime,
    maximum_protocols: int = 32,
    executor: IsolatedResearchExecutor | None = None,
) -> dict[str, Any]:
    """Consume a generated Intelligence Lab queue through the fixed allowlist."""
    timestamp = utc(generated_at)
    if maximum_protocols < 1:
        raise AutoresearchValidationError("maximum_protocols must be positive")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    if not isinstance(queue, dict):
        raise AutoresearchValidationError("research queue must be an object")
    queue_id = str(queue.get("queue_id") or "")
    semantic_queue = {key: value for key, value in queue.items() if key != "queue_id"}
    if queue_id != digest_json(semantic_queue):
        raise AutoresearchValidationError("research queue identity is invalid")
    if bool(queue.get("automatic_positive_promotion")) or bool(
        queue.get("execution_authority")
    ):
        raise AutoresearchValidationError("research queue carries forbidden authority")
    protocols = queue.get("protocols") or []
    if not isinstance(protocols, list):
        raise AutoresearchValidationError("research queue protocols must be a list")
    selected = protocols[:maximum_protocols]
    journal = ResearchJournal(journal_path)
    coordinator = ResearchCoordinator(journal, executor=executor)
    results: list[CoordinationResult] = []
    source_protocol_ids: list[str] = []
    for index, protocol in enumerate(selected):
        if not isinstance(protocol, dict):
            raise AutoresearchValidationError("research protocol must be an object")
        source_protocol_ids.append(str(protocol.get("experiment_id") or ""))
        definition = intelligence_definition_from_protocol(
            protocol,
            seed=index,
        )
        results.append(
            coordinator.run(
                definition,
                evidence,
                observed_at=timestamp,
            )
        )
    if any(not item.reused for item in results):
        journal.checkpoint(occurred_at=timestamp)
    verdict_counts = {
        verdict.value: sum(
            item.receipt.verdict is verdict for item in results
        )
        for verdict in EvaluationVerdict
    }
    all_controls = all(
        item.receipt.negative_controls_passed for item in results
    )
    summary = journal.summary()
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": iso(timestamp),
        "status": (
            "COMPLETE"
            if len(selected) == len(protocols)
            else "PARTIAL"
        ),
        "research_validation_status": (
            "ACCUMULATING"
            if verdict_counts[EvaluationVerdict.PASS.value] == 0
            else "CANDIDATE_EVIDENCE_PRESENT"
        ),
        "queue_id": queue_id,
        "source_report_id": queue.get("source_report_id"),
        "protocols_seen": len(protocols),
        "protocols_consumed": len(selected),
        "protocols_deferred": max(0, len(protocols) - len(selected)),
        "source_protocol_ids": source_protocol_ids,
        "runs_created": sum(not item.reused for item in results),
        "runs_reused": sum(item.reused for item in results),
        "verdict_counts": verdict_counts,
        "negative_controls_passed": all_controls,
        "journal_tip": summary,
        "validated_theories": 0,
        "private_item_details": None,
        "source_edits_applied": False,
        "runtime_application": False,
        "automatic_promotion": False,
        "execution_authority": False,
        "capital_authority": False,
        "orders_placed": False,
    }
    report["report_id"] = digest_json(report)
    _atomic_json(report_path, report)
    return report


__all__ = [
    "CoordinationResult",
    "ResearchCoordinator",
    "consume_intelligence_queue",
]
