from __future__ import annotations

from dataclasses import replace

import pytest

from dummy.benchmarks import BenchmarkDomain, benchmark_catalog
from dummy.claims import (
    CLAIM_DEFINITIONS,
    ClaimEvidence,
    ClaimVerdict,
    EvidenceReality,
    EvidenceRequirement,
    current_governance_evidence,
    review_claims,
)
from dummy.world_model.models import digest_json
from scripts.run_vnext_phase8_audit import build_outputs


def _evidence(
    requirement: EvidenceRequirement,
    reality: EvidenceReality,
    *,
    observed_cases: int = 0,
    event_clusters: int = 0,
) -> ClaimEvidence:
    empirical = reality is EvidenceReality.EMPIRICAL
    semantic = {
        "schema_version": 1,
        "requirement": requirement.value,
        "reality": reality.value,
        "source_artifact": "tests/independent-evidence.json",
        "assertion": "independently verified test evidence",
        "verified": True,
        "point_in_time": empirical,
        "held_out": empirical,
        "observed_cases": observed_cases,
        "event_clusters": event_clusters,
        "candidate_controlled": False,
        "issuer": "PROTECTED_EXTERNAL_AUDIT",
    }
    return ClaimEvidence(
        evidence_id=digest_json(semantic),
        requirement=requirement,
        reality=reality,
        source_artifact=semantic["source_artifact"],
        assertion=semantic["assertion"],
        verified=True,
        point_in_time=empirical,
        held_out=empirical,
        observed_cases=observed_cases,
        event_clusters=event_clusters,
    )


def test_benchmark_catalog_matches_all_six_master_plan_domains() -> None:
    metrics = benchmark_catalog()
    assert len(metrics) == 32
    assert len({item.metric_id for item in metrics}) == 32
    assert {
        domain: sum(item.domain is domain for item in metrics)
        for domain in BenchmarkDomain
    } == {
        BenchmarkDomain.FORECAST_QUALITY: 5,
        BenchmarkDomain.MULTI_AGENT_VALUE: 5,
        BenchmarkDomain.METACOGNITIVE_QUALITY: 6,
        BenchmarkDomain.EXECUTION_REALISM: 5,
        BenchmarkDomain.EVOLUTION_QUALITY: 5,
        BenchmarkDomain.GOVERNANCE_QUALITY: 6,
    }


def test_claim_catalog_and_current_review_are_complete_and_honest() -> None:
    outputs = build_outputs()
    review = outputs["VNEXT_PHASE8_CLAIM_REVIEW.json"]
    assert len(CLAIM_DEFINITIONS) == 8
    assert len({item.code for item in CLAIM_DEFINITIONS}) == 8
    assert sum(item.empirical for item in CLAIM_DEFINITIONS) == 6
    assert review["claim_count"] == 8
    assert review["performance_supported_count"] == 0
    assert review["governance_supported_count"] == 2
    assert review["insufficient_evidence_count"] == 6
    assert review["material_improvement_established"] is False
    assert review["automatic_promotion"] is False


def test_unverified_or_synthetic_assertions_cannot_support_claims() -> None:
    unverified = review_claims(current_governance_evidence())
    assert unverified["insufficient_evidence_count"] == 8
    assert unverified["governance_supported_count"] == 0

    synthetic = tuple(
        _evidence(requirement, EvidenceReality.SYNTHETIC)
        for requirement in EvidenceRequirement
    )
    result = review_claims(synthetic)
    assert result["performance_supported_count"] == 0
    assert all(
        item["verdict"] != ClaimVerdict.SUPPORTED.value
        for item in result["reviews"]
    )


def test_claim_evidence_rejects_candidate_control_and_fake_empiricism() -> None:
    valid = _evidence(
        EvidenceRequirement.CALIBRATION,
        EvidenceReality.EMPIRICAL,
        observed_cases=20,
        event_clusters=20,
    )
    with pytest.raises(ValueError, match="protected external audit"):
        replace(valid, candidate_controlled=True)
    with pytest.raises(ValueError, match="point-in-time held-out clusters"):
        replace(valid, point_in_time=False)
