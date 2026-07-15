"""Current externally verified structural evidence for Claims 7 and 8."""

from __future__ import annotations

from dummy.claims.schema import ClaimEvidence, EvidenceReality, EvidenceRequirement
from dummy.world_model.models import digest_json


def _evidence(
    requirement: EvidenceRequirement,
    reality: EvidenceReality,
    source_artifact: str,
    assertion: str,
    *,
    verified: bool,
) -> ClaimEvidence:
    semantic = {
        "schema_version": 1,
        "requirement": requirement.value,
        "reality": reality.value,
        "source_artifact": source_artifact,
        "assertion": assertion,
        "verified": verified,
        "point_in_time": False,
        "held_out": False,
        "observed_cases": 0,
        "event_clusters": 0,
        "candidate_controlled": False,
        "issuer": "PROTECTED_EXTERNAL_AUDIT",
    }
    return ClaimEvidence(
        evidence_id=digest_json(semantic),
        requirement=requirement,
        reality=reality,
        source_artifact=source_artifact,
        assertion=assertion,
        verified=verified,
        point_in_time=False,
        held_out=False,
        observed_cases=0,
        event_clusters=0,
    )


def current_governance_evidence(
    *,
    verified_requirements: frozenset[EvidenceRequirement] = frozenset(),
) -> tuple[ClaimEvidence, ...]:
    return tuple(
        sorted(
            (
                _evidence(
                    EvidenceRequirement.FILL_TRUTH_SEPARATION,
                    EvidenceReality.GOVERNANCE,
                    "docs/VNEXT_PHASE6_MEMORY_POLICY.json",
                    "verified settlement, witnessed fill, and simulated fill are distinct "
                    "realities; simulated fills cannot become realized capital PnL",
                    verified=EvidenceRequirement.FILL_TRUTH_SEPARATION
                    in verified_requirements,
                ),
                _evidence(
                    EvidenceRequirement.EXECUTION_REALISM,
                    EvidenceReality.GOVERNANCE,
                    "docs/VNEXT_PHASE6_EVOLUTION_POLICY.json",
                    "forecast evaluation and fill truth are separate and no runtime "
                    "execution is applied",
                    verified=EvidenceRequirement.EXECUTION_REALISM
                    in verified_requirements,
                ),
                _evidence(
                    EvidenceRequirement.DETERMINISTIC_REPLAY,
                    EvidenceReality.MECHANICAL,
                    "docs/VNEXT_PHASE7_ARENA_REPRODUCIBILITY.json",
                    "all canonical mechanical arena cases replay byte-identically",
                    verified=EvidenceRequirement.DETERMINISTIC_REPLAY
                    in verified_requirements,
                ),
                _evidence(
                    EvidenceRequirement.GOVERNANCE_TESTS,
                    EvidenceReality.GOVERNANCE,
                    "docs/VNEXT_PROTECTED_SURFACES.json",
                    "truth, evaluation, promotion, credentials, and execution remain "
                    "outside candidate mutation",
                    verified=EvidenceRequirement.GOVERNANCE_TESTS
                    in verified_requirements,
                ),
                _evidence(
                    EvidenceRequirement.AUTHORITY_NONEXPANSION,
                    EvidenceReality.GOVERNANCE,
                    "docs/VNEXT_PHASE7_HOMEOSTASIS_POLICY.json",
                    "research interventions and observatory projections cannot increase "
                    "authority",
                    verified=EvidenceRequirement.AUTHORITY_NONEXPANSION
                    in verified_requirements,
                ),
                _evidence(
                    EvidenceRequirement.CREDENTIAL_ISOLATION,
                    EvidenceReality.GOVERNANCE,
                    "tests/test_vnext_import_boundaries.py",
                    "vNext research packages are statically prohibited from importing "
                    "credential and execution modules",
                    verified=EvidenceRequirement.CREDENTIAL_ISOLATION
                    in verified_requirements,
                ),
            ),
            key=lambda item: item.evidence_id,
        )
    )


__all__ = ["current_governance_evidence"]
