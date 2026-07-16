from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dummy.intelligence_lab import (
    CognitiveOperator,
    GraphKind,
    IntelligenceLabValidationError,
    ScientificMemory,
    TheoryMaturity,
    evaluate_theory,
    make_replication_receipt,
    run_intelligence_research_cycle,
)
from dummy.intelligence_lab.models import make_observation


def _receipt(
    hypothesis_id: str,
    domain_id: str,
    independence_key: str,
):
    return make_replication_receipt(
        hypothesis_id=hypothesis_id,
        domain_id=domain_id,
        independence_key=independence_key,
        effect_lower_bound=0.01,
        calibration_noninferior=True,
        deterministic_replay=True,
        reward_hack_free=True,
        fixed_cost_noninferior=True,
        future_leakage_free=True,
        forced_coverage_free=True,
        source_correlation_free=True,
        execution_truth_noninferior=True,
        complexity_noninferior=True,
    )


def test_observations_are_content_addressed_and_tamper_evident() -> None:
    observation = make_observation(
        domain_id="test.domain",
        graph_kind=GraphKind.UNKNOWN,
        statement="A causal relationship remains unknown.",
        observed_at="2026-07-15T12:00:00Z",
        confidence=0.8,
        evidence_ids=("evidence-1",),
        attributes={"missing_evidence": ("replication",)},
    )
    assert len(observation.observation_id) == 64
    payload = observation.to_dict()
    payload["statement"] = "tampered"
    with pytest.raises(IntelligenceLabValidationError, match="does not match"):
        type(observation)(
            observation_id=observation.observation_id,
            domain_id=observation.domain_id,
            graph_kind=observation.graph_kind,
            statement=payload["statement"],
            observed_at=observation.observed_at,
            confidence=observation.confidence,
            evidence_ids=observation.evidence_ids,
            attributes=observation.attributes,
        )


def test_scientific_memory_is_hash_chained_and_idempotent(tmp_path: Path) -> None:
    memory = ScientificMemory(tmp_path / "scientific.jsonl")
    first, created = memory.append_unique(
        record_type="observation",
        payload={"claim": "one", "evidence": ["a"]},
    )
    repeated, created_again = memory.append_unique(
        record_type="observation",
        payload={"claim": "one", "evidence": ["a"]},
    )
    second, _ = memory.append_unique(
        record_type="failure",
        payload={"claim": "two", "evidence": ["b"]},
    )
    assert created is True
    assert created_again is False
    assert repeated == first
    assert second.previous_hash == first.entry_hash
    assert len(memory.read_verified()) == 2

    rows = memory.path.read_text(encoding="utf-8").splitlines()
    damaged = json.loads(rows[0])
    damaged["payload"]["claim"] = "rewritten"
    rows[0] = json.dumps(damaged)
    memory.path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(IntelligenceLabValidationError, match="tampered"):
        memory.read_verified()


def test_theory_and_law_require_independent_cross_domain_replication() -> None:
    hypothesis_id = "hypothesis-1"
    one_domain = tuple(
        _receipt(hypothesis_id, "forecasting", f"seed-{index}")
        for index in range(3)
    )
    assessment = evaluate_theory(
        hypothesis_id=hypothesis_id,
        claim="method improves reasoning",
        receipts=one_domain,
    )
    assert assessment["maturity"] == TheoryMaturity.HYPOTHESIS.value

    provisional = evaluate_theory(
        hypothesis_id=hypothesis_id,
        claim="method improves reasoning",
        receipts=(*one_domain[:2], _receipt(hypothesis_id, "security", "seed-3")),
    )
    assert provisional["maturity"] == TheoryMaturity.PROVISIONAL_THEORY.value

    law_receipts = tuple(
        _receipt(hypothesis_id, ("forecasting", "security", "coding")[index % 3], f"independent-{index}")
        for index in range(6)
    )
    law = evaluate_theory(
        hypothesis_id=hypothesis_id,
        claim="method improves reasoning",
        receipts=law_receipts,
    )
    assert law["maturity"] == TheoryMaturity.GENERAL_LAW.value


def test_forecasting_cycle_generates_research_without_inventing_results(
    tmp_path: Path,
) -> None:
    campaign = {
        "genuine_private_candidate_trials": 5,
        "private_survivors": 1,
        "external_survivors": 1,
    }
    multi = {
        "report_id": "multi-proof",
        "discovered_cohorts": 3,
        "campaigns_completed": 1,
        "schedule": [
            {
                "scope": "crypto|btc|price_ladder|unknown",
                "status": "BLOCKED_MISSING_HORIZON_PROVENANCE",
            }
        ],
        "campaigns": [{"scope": "crypto|btc|price_ladder|1h", "campaign": campaign}],
    }
    forward = {
        "report_id": "forward-proof",
        "forward_paper_candidate_settlements": 0,
    }
    ignition = {
        "report_id": "ignition-proof",
        "highest_supported_recursive_improvement_level": 0,
    }
    report = run_intelligence_research_cycle(
        multi_cohort_report=multi,
        forward_report=forward,
        ignition_report=ignition,
        output_dir=tmp_path,
        observed_at=datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
    )
    assert report["cognitive_state"]["opportunities"] >= 3
    assert report["cognitive_state"]["proposed_experiments"] >= 9
    assert report["cognitive_state"]["completed_experiments"] == 0
    assert report["cognitive_state"]["provisional_theories"] == 0
    assert report["claims"]["new_intelligence_method_validated"] is False
    assert report["highest_supported_level"] == 0
    assert report["automatic_positive_promotion"] is False
    assert report["execution_authority"] is False
    assert {item.value for item in CognitiveOperator}.issuperset(
        hypothesis["operator"] for hypothesis in report["hypotheses"]
    )
    assert (tmp_path / "observatory_report.json").exists()
    assert len(ScientificMemory(tmp_path / "scientific_memory.jsonl").read_verified()) > 0
