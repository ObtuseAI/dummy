from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dummy.autoresearch.control_models import (
    CandidateStage,
    EvidenceSnapshot,
    ResearchBudgetPolicy,
    RunStatus,
)
from dummy.autoresearch.isolated_executor import WorkerExecution
from dummy.autoresearch.models import AutoresearchValidationError
from dummy.autoresearch.research_coordinator import (
    ResearchCoordinator,
    consume_intelligence_queue,
)
from dummy.autoresearch.research_journal import ResearchJournal
from dummy.autoresearch.research_plugins import (
    evolution_definition,
    intelligence_definition_from_protocol,
)
from dummy.world_model.models import digest_json


NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)


def _protocol(intervention: str = "preregistered_analogy_cognitive_pipeline"):
    return {
        "schema_version": 1,
        "experiment_id": "source-experiment",
        "hypothesis_id": "source-hypothesis",
        "domain_id": "dummy.forecasting",
        "intervention": intervention,
        "control": "frozen_current_champion_cognitive_pipeline",
        "private_metrics": [
            "calibration_noninferiority",
            "fixed_cost_private_score",
        ],
        "required_partitions": [
            "visible_development",
            "private_selection",
            "external_generalization",
            "forward_validation",
        ],
        "compute_budget": 1000.0,
        "replication_seed_count": 3,
        "status": "proposed",
        "candidate_controls_evaluator": False,
        "authority": "SIMULATE_MAXIMUM",
    }


def _evidence(captured_at: datetime = NOW) -> EvidenceSnapshot:
    return EvidenceSnapshot.create(
        domain_id="dummy.forecasting",
        captured_at=captured_at,
        source_ids=("campaign-proof", "forward-proof"),
        source_family_ids=("campaign", "forward"),
        payload={
            "settlements": 0,
            "execution_authority": False,
            "automatic_promotion": False,
        },
        point_in_time_verified=True,
        settlement_verified=True,
    )


def _queue(path: Path, protocols: list[dict[str, object]]) -> None:
    body = {
        "schema_version": 1,
        "generated_at": NOW.isoformat(),
        "source_report_id": "observatory-proof",
        "scheduling_policy": "content_id",
        "fixed_compute_budget_per_experiment": 1000.0,
        "total_proposed_compute_budget": 1000.0 * len(protocols),
        "protocols": protocols,
        "automatic_execution_scope": "PROTECTED_SHADOW_SIMULATION_ONLY",
        "automatic_positive_promotion": False,
        "execution_authority": False,
    }
    body["queue_id"] = digest_json(body)
    path.write_text(json.dumps(body), encoding="utf-8")


def test_budget_policy_is_zero_network_and_zero_credentials() -> None:
    policy = ResearchBudgetPolicy()
    assert policy.network_access is False
    assert policy.credential_access is False
    assert policy.maximum_cost_microunits == 0
    assert policy.maximum_network_requests == 0
    assert policy.maximum_credentials == 0
    with pytest.raises(AutoresearchValidationError, match="network"):
        ResearchBudgetPolicy(network_access=True)
    with pytest.raises(AutoresearchValidationError, match="credential"):
        ResearchBudgetPolicy(credential_access=True)


def test_transactional_journal_deduplicates_and_detects_tampering(
    tmp_path: Path,
) -> None:
    journal = ResearchJournal(tmp_path / "research.sqlite3")
    definition = intelligence_definition_from_protocol(_protocol())
    assert journal.store_definition(
        record_id=definition.definition_id,
        record_type="ResearchDefinition",
        semantic=definition.semantic_dict(),
        stored_at=NOW,
    )
    assert not journal.store_definition(
        record_id=definition.definition_id,
        record_type="ResearchDefinition",
        semantic=definition.semantic_dict(),
        stored_at=NOW + timedelta(seconds=1),
    )
    assert journal.summary()["definition_count"] == 1
    assert journal.summary()["event_count"] == 1

    with sqlite3.connect(journal.path) as connection:
        connection.execute("DROP TRIGGER research_events_immutable_update")
        connection.execute(
            "UPDATE research_events SET subject_id = 'tampered' WHERE sequence = 0"
        )
    with pytest.raises(AutoresearchValidationError, match="tampered"):
        journal.read_events_verified()


def test_queue_is_consumed_in_isolated_worker_and_semantically_deduplicated(
    tmp_path: Path,
) -> None:
    queue_path = tmp_path / "research_queue.json"
    journal_path = tmp_path / "research_journal.sqlite3"
    report_path = tmp_path / "research_control_plane_report.json"
    _queue(queue_path, [_protocol()])

    first = consume_intelligence_queue(
        queue_path=queue_path,
        journal_path=journal_path,
        report_path=report_path,
        evidence=_evidence(),
        generated_at=NOW,
    )
    assert first["status"] == "COMPLETE"
    assert first["runs_created"] == 1
    assert first["runs_reused"] == 0
    assert first["negative_controls_passed"] is True
    assert first["verdict_counts"]["INCONCLUSIVE"] == 1
    assert first["execution_authority"] is False
    assert first["automatic_promotion"] is False

    # Scheduler observation time does not mint another run when the semantic
    # evidence, candidate, plugin, and evaluator are unchanged.
    second = consume_intelligence_queue(
        queue_path=queue_path,
        journal_path=journal_path,
        report_path=report_path,
        evidence=_evidence(NOW + timedelta(hours=1)),
        generated_at=NOW + timedelta(hours=1),
    )
    assert second["runs_created"] == 0
    assert second["runs_reused"] == 1

    journal = ResearchJournal(journal_path)
    run_events = [
        item
        for item in journal.read_events_verified()
        if item.event_type == "RESEARCH_RUN"
    ]
    assert len(run_events) == 1
    sandbox = run_events[0].payload["result"]["sandbox"]
    assert sandbox["environment_policy"] == "EXPLICIT_CODE_OWNED_ONLY"
    assert sandbox["network_access"] is False
    assert "environment_keys" not in sandbox


def test_unregistered_intelligence_intervention_is_blocked(tmp_path: Path) -> None:
    queue_path = tmp_path / "research_queue.json"
    _queue(queue_path, [_protocol("run_arbitrary_python")])
    report = consume_intelligence_queue(
        queue_path=queue_path,
        journal_path=tmp_path / "journal.sqlite3",
        report_path=tmp_path / "report.json",
        evidence=_evidence(),
        generated_at=NOW,
    )
    assert report["status"] == "COMPLETE"
    assert report["verdict_counts"]["BLOCKED"] == 1
    assert report["negative_controls_passed"] is True


class _FailedForwardExecutor:
    def execute(self, definition, evidence) -> WorkerExecution:
        checks = {
            name: True for name in definition.required_control_ids
        }
        return WorkerExecution(
            status=RunStatus.COMPLETE,
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=1),
            wall_seconds=1.0,
            result={
                "worker_status": "COMPLETE",
                "outcome": "INCONCLUSIVE",
                "reason": "FAILED_FORWARD_EPOCH",
                "candidate_id": definition.candidate_id,
                "negative_controls": {"checks": checks, "passed": True},
                "evolution_summary": {"forward_failed": True},
                "validated_effect": False,
                "source_edit_applied": False,
                "runtime_application": False,
                "automatic_promotion": False,
                "execution_authority": False,
                "capital_authority": False,
                "orders_placed": False,
            },
        )


def test_failed_forward_evolution_candidate_is_retired_without_promotion(
    tmp_path: Path,
) -> None:
    definition = evolution_definition(
        evidence_fingerprint="evidence-proof",
        candidate_id="research-genome-candidate",
        population_size=8,
        bootstrap_simulations=100,
    )
    coordinator = ResearchCoordinator(
        ResearchJournal(tmp_path / "journal.sqlite3"),
        executor=_FailedForwardExecutor(),
    )
    result = coordinator.run(definition, _evidence(), observed_at=NOW)
    stages = [event.stage for event in result.state_events]
    assert stages == [
        CandidateStage.PROPOSED,
        CandidateStage.PREREGISTERED,
        CandidateStage.DEV_EVALUATED,
        CandidateStage.RETIRED,
    ]
    assert result.receipt.human_review_required is True
    assert result.receipt.to_dict()["automatic_promotion"] is False
