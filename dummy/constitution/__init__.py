"""Sealed constitutional primitives for DUMMY vNext."""

from dummy.constitution.authority import (
    CAPITAL_AUTHORITIES,
    RESEARCH_AUTHORITY_CEILING,
    Authority,
    AuthorityViolation,
    assert_authority_at_most,
    can_delegate,
)
from dummy.constitution.invariants import (
    CONSTITUTIONAL_INVARIANTS,
    ConstitutionalInvariant,
    InvariantCode,
)
from dummy.constitution.mutation_protection import (
    EVOLVABLE_ROOTS,
    PROTECTED_SURFACES,
    MutationDecision,
    ProtectedSurface,
    SurfaceCategory,
    evaluate_mutation_proposal,
    protected_manifest_digest,
)

__all__ = [
    "CAPITAL_AUTHORITIES",
    "CONSTITUTIONAL_INVARIANTS",
    "EVOLVABLE_ROOTS",
    "PROTECTED_SURFACES",
    "RESEARCH_AUTHORITY_CEILING",
    "Authority",
    "AuthorityViolation",
    "ConstitutionalInvariant",
    "InvariantCode",
    "MutationDecision",
    "ProtectedSurface",
    "SurfaceCategory",
    "assert_authority_at_most",
    "can_delegate",
    "evaluate_mutation_proposal",
    "protected_manifest_digest",
]
