"""DUMMY vNext protected claim-specific evidence program."""

from dummy.claims.catalog import CLAIM_DEFINITIONS
from dummy.claims.evaluator import CLAIM_EVALUATOR_VERSION, review_claims
from dummy.claims.evidence import current_governance_evidence
from dummy.claims.schema import (
    ClaimCode,
    ClaimDefinition,
    ClaimEvidence,
    ClaimReview,
    ClaimVerdict,
    EvidenceReality,
    EvidenceRequirement,
)

__all__ = [
    "CLAIM_DEFINITIONS",
    "CLAIM_EVALUATOR_VERSION",
    "ClaimCode",
    "ClaimDefinition",
    "ClaimEvidence",
    "ClaimReview",
    "ClaimVerdict",
    "EvidenceReality",
    "EvidenceRequirement",
    "current_governance_evidence",
    "review_claims",
]
