from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from dummy.autoresearch import protected_worker
from dummy.autoresearch.control_models import (
    EvidenceSnapshot,
    ResearchBudgetPolicy,
    ResearchDefinition,
    ResearchKind,
)
from dummy.autoresearch.negative_controls import CONTROL_IDS
from dummy.autoresearch.research_plugins import (
    evolution_definition,
    evolution_evidence_snapshot,
    intelligence_definition_from_protocol,
)

NOW = datetime(2026, 7, 26, 8, tzinfo=timezone.utc)


def _protocol(intervention: str) -> dict[str, object]:
    return {
        "experiment_id": "worker-contract",
        "hypothesis_id": "bounded-worker",
        "domain_id": "dummy.forecasting",
        "intervention": intervention,
        "control": "frozen_champion",
        "private_metrics": ["calibration_noninferiority"],
        "required_partitions": ["private_selection"],
        "replication_seed_count": 3,
        "candidate_controls_evaluator": False,
        "authority": "SIMULATE_MAXIMUM",
    }


def _evidence() -> EvidenceSnapshot:
    return EvidenceSnapshot.create(
        domain_id="dummy.forecasting",
        captured_at=NOW,
        source_ids=("worker-source",),
        source_family_ids=("worker-family",),
        payload={
            "settlements": 0,
            "execution_authority": False,
            "automatic_promotion": False,
        },
        point_in_time_verified=True,
        settlement_verified=True,
    )


def _request(
    definition: ResearchDefinition,
    evidence: EvidenceSnapshot,
) -> dict[str, object]:
    return {
        "definition": definition.to_dict(),
        "evidence": evidence.to_dict(),
    }


def test_worker_allows_only_registered_code_owned_intelligence() -> None:
    registered = intelligence_definition_from_protocol(
        _protocol("preregistered_analogy_cognitive_pipeline")
    )
    accepted = protected_worker.execute(_request(registered, _evidence()))
    assert accepted["worker_status"] == "COMPLETE"
    assert accepted["outcome"] == "INCONCLUSIVE"
    assert accepted["negative_controls"]["passed"] is True
    assert accepted["validated_effect"] is False
    assert accepted["private_item_details"] is None

    unregistered = intelligence_definition_from_protocol(
        _protocol("run_arbitrary_python")
    )
    blocked = protected_worker.execute(_request(unregistered, _evidence()))
    assert blocked["worker_status"] == "BLOCKED"
    assert blocked["reason"] == "BLOCKED_NO_REGISTERED_EXECUTOR"
    assert blocked["validated_effect"] is False

    unknown = ResearchDefinition.create(
        plugin_id="dummy.unregistered",
        plugin_version="v1",
        kind=ResearchKind.INTELLIGENCE_PROTOCOL,
        hypothesis_id="unknown-plugin",
        candidate_id="unknown-candidate",
        evaluator_id="protected-evaluator",
        parameters={},
        required_control_ids=CONTROL_IDS,
        seed=0,
        budget=ResearchBudgetPolicy(maximum_wall_seconds=2),
    )
    denied = protected_worker.execute(_request(unknown, _evidence()))
    assert denied["worker_status"] == "BLOCKED"
    assert denied["reason"] == "PLUGIN_NOT_ALLOWLISTED"
    assert denied["negative_controls"]["passed"] is False


def test_worker_evolution_summary_preserves_review_boundary(monkeypatch) -> None:
    definition = evolution_definition(
        evidence_fingerprint="worker-evidence",
        candidate_id="candidate-original",
        population_size=8,
        bootstrap_simulations=100,
    )
    evidence = evolution_evidence_snapshot(rows=[], captured_at=NOW)

    def _run_evolution_lab(
        rows,
        *,
        previous_report,
        as_of,
        population_size,
        bootstrap_simulations,
    ):
        assert rows == []
        assert previous_report == {}
        assert as_of == NOW
        assert population_size == 8
        assert bootstrap_simulations == 100
        return {
            "generation": 2,
            "status": "RESEARCH_ONLY",
            "evidence": {"settled_clusters": 3},
            "research_leader": "candidate-reviewed",
            "active_research_candidate": {"genome_id": "candidate-reviewed"},
            "retrospective_out_of_sample": {
                "passes_research_epoch_gate": True,
            },
            "forward_ratchet": {
                "ready_for_explicit_shadow_review": True,
                "failed_research_epoch": False,
            },
            "authority": {
                "automatic_promotion": False,
                "execution": False,
            },
            "evidence_quarantine": {},
        }

    monkeypatch.setattr(
        "autonomy.evolution_lab.run_evolution_lab",
        _run_evolution_lab,
    )
    result = protected_worker.execute(_request(definition, evidence))

    assert result["worker_status"] == "COMPLETE"
    assert result["outcome"] == "PASS"
    assert result["reason"] == "READY_FOR_HUMAN_RESEARCH_REVIEW"
    assert result["candidate_id"] == "candidate-reviewed"
    assert result["validated_effect"] is True
    assert result["evolution_summary"]["forward_gate"] is True
    assert result["evolution_summary"]["authority"]["execution"] is False


def test_worker_main_emits_bounded_success_and_failure_contracts(
    monkeypatch,
) -> None:
    definition = intelligence_definition_from_protocol(
        _protocol("preregistered_analogy_cognitive_pipeline")
    )
    request = json.dumps(_request(definition, _evidence())).encode("utf-8")
    output = io.StringIO()
    monkeypatch.setattr(protected_worker, "_install_network_guard", lambda: None)
    monkeypatch.setattr(
        protected_worker.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(request)),
    )
    monkeypatch.setattr(protected_worker.sys, "stdout", output)

    assert protected_worker.main() == 0
    success = json.loads(output.getvalue())
    assert success["sandbox"]["isolated_process"] is True
    assert success["sandbox"]["network_access"] is False
    assert success["execution_authority"] is False
    assert success["orders_placed"] is False

    failed_output = io.StringIO()
    monkeypatch.setattr(
        protected_worker.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(b"[]")),
    )
    monkeypatch.setattr(protected_worker.sys, "stdout", failed_output)

    assert protected_worker.main() == 2
    failure = json.loads(failed_output.getvalue())
    assert failure["worker_status"] == "FAILED"
    assert failure["reason"] == "ValueError"
    assert failure["execution_authority"] is False
    assert failure["orders_placed"] is False


def test_worker_network_guard_denies_all_socket_entry_points(monkeypatch) -> None:
    for name in ("socket", "create_connection", "getaddrinfo"):
        original = getattr(protected_worker.socket, name)
        monkeypatch.setattr(protected_worker.socket, name, original)

    protected_worker._install_network_guard()

    with pytest.raises(PermissionError, match="network access is disabled"):
        protected_worker.socket.socket()
    with pytest.raises(PermissionError, match="network access is disabled"):
        protected_worker.socket.create_connection(("127.0.0.1", 1))
    with pytest.raises(PermissionError, match="network access is disabled"):
        protected_worker.socket.getaddrinfo("localhost", 1)
