"""Protected external evaluator for the eight required internal claims."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from dummy.claims.catalog import CLAIM_DEFINITIONS
from dummy.claims.schema import (
    ClaimEvidence,
    ClaimReview,
    ClaimVerdict,
    EvidenceReality,
)
from dummy.world_model.models import digest_json


CLAIM_EVALUATOR_VERSION = "phase8-claim-evaluator-v1"


def review_claims(evidence: tuple[ClaimEvidence, ...]) -> dict[str, Any]:
    by_requirement: dict[object, list[ClaimEvidence]] = defaultdict(list)
    for item in evidence:
        if item.verified:
            by_requirement[item.requirement].append(item)

    reviews: list[ClaimReview] = []
    for definition in CLAIM_DEFINITIONS:
        satisfied = []
        evidence_ids: set[str] = set()
        max_clusters = 0
        for requirement in definition.requirements:
            candidates = by_requirement.get(requirement, [])
            if definition.empirical:
                candidates = [
                    item
                    for item in candidates
                    if item.reality is EvidenceReality.EMPIRICAL
                    and item.point_in_time
                    and item.held_out
                ]
            else:
                candidates = [
                    item
                    for item in candidates
                    if item.reality in {EvidenceReality.GOVERNANCE, EvidenceReality.MECHANICAL}
                ]
            if candidates:
                satisfied.append(requirement)
                evidence_ids.update(item.evidence_id for item in candidates)
                max_clusters = max(max_clusters, *(item.event_clusters for item in candidates))
        missing = tuple(item for item in definition.requirements if item not in satisfied)
        blockers = [f"missing:{item.value}" for item in missing]
        if definition.empirical and max_clusters < definition.minimum_event_clusters:
            blockers.append(
                f"event_clusters:{max_clusters}<{definition.minimum_event_clusters}"
            )
        if blockers:
            verdict = ClaimVerdict.INSUFFICIENT_EVIDENCE
        elif definition.empirical:
            verdict = ClaimVerdict.SUPPORTED
        else:
            verdict = ClaimVerdict.SUPPORTED_GOVERNANCE_ONLY
        semantic = {
            "schema_version": 1,
            "definition": definition.to_dict(),
            "verdict": verdict.value,
            "evidence_ids": sorted(evidence_ids),
            "satisfied_requirements": sorted(item.value for item in satisfied),
            "missing_requirements": sorted(item.value for item in missing),
            "blockers": sorted(blockers),
            "automatic_promotion": False,
        }
        reviews.append(
            ClaimReview(
                review_id=digest_json(semantic),
                definition=definition,
                verdict=verdict,
                evidence_ids=tuple(evidence_ids),
                satisfied_requirements=tuple(satisfied),
                missing_requirements=missing,
                blockers=tuple(blockers),
            )
        )
    reviews.sort(key=lambda item: item.definition.code.value)
    body: dict[str, Any] = {
        "schema_version": 1,
        "phase": 8,
        "evaluator_version": CLAIM_EVALUATOR_VERSION,
        "reviews": [item.to_dict() for item in reviews],
        "evidence": [item.to_dict() for item in sorted(evidence, key=lambda item: item.evidence_id)],
        "claim_count": len(reviews),
        "performance_supported_count": sum(
            item.verdict is ClaimVerdict.SUPPORTED for item in reviews
        ),
        "governance_supported_count": sum(
            item.verdict is ClaimVerdict.SUPPORTED_GOVERNANCE_ONLY for item in reviews
        ),
        "insufficient_evidence_count": sum(
            item.verdict is ClaimVerdict.INSUFFICIENT_EVIDENCE for item in reviews
        ),
        "material_improvement_established": all(
            item.verdict is ClaimVerdict.SUPPORTED
            for item in reviews
            if item.definition.empirical
        ),
        "automatic_promotion": False,
        "promotion_authority": "HUMAN_ONLY",
    }
    body["program_id"] = digest_json(body)
    return body


__all__ = ["CLAIM_EVALUATOR_VERSION", "review_claims"]
